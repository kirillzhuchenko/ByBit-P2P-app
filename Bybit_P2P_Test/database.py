"""
Database module for tracking matched orders between ByBit P2P and Wise transfers.
Stores verification data to prevent double-matching and maintain audit trail.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import IntEnum
from contextlib import contextmanager


class OrderSide(IntEnum):
    """Order side enum matching main code"""
    BUY = 0
    SELL = 1


class VerificationSource(IntEnum):
    """Source of verification"""
    WISE_INCOMING = 1  # Incoming Wise transfer (for SELL orders)
    WISE_OUTGOING = 2  # Outgoing Wise transfer (for BUY orders)


class VerificationStatus(IntEnum):
    """Verification status of orders"""
    NOT_VERIFIED = 0
    VERIFIED = 1


class Database:
    """Database handler for matched order tracking"""

    def __init__(self, db_path: str = "matched_orders.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create matched_orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matched_orders (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL UNIQUE,
                    order_side INTEGER NOT NULL,
                    order_amount REAL NOT NULL,
                    counterparty_name TEXT NOT NULL,
                    wise_transfer_reference TEXT,
                    wise_amount REAL,
                    wise_direction TEXT,
                    matched_at TIMESTAMP NOT NULL,
                    verification_source INTEGER,
                    verification_status INTEGER NOT NULL DEFAULT 0,
                    CONSTRAINT chk_order_side CHECK (order_side IN (0, 1)),
                    CONSTRAINT chk_verification_source CHECK (verification_source IN (1, 2) OR verification_source IS NULL),
                    CONSTRAINT chk_wise_direction CHECK (wise_direction IN ('CREDIT', 'DEBIT') OR wise_direction IS NULL),
                    CONSTRAINT chk_verification_status CHECK (verification_status IN (0, 1))
                )
            """)

            # Create indexes for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_order_id 
                ON matched_orders(order_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wise_reference 
                ON matched_orders(wise_transfer_reference)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_matched_at 
                ON matched_orders(matched_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_verification_status 
                ON matched_orders(verification_status)
            """)

            conn.commit()

    def add_order(
        self,
        order_id: str,
        order_side: OrderSide,
        order_amount: float,
        counterparty_name: str,
        verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    ) -> int:
        """
        Add a new order to database (verified or not verified).

        Args:
            order_id: ByBit order ID
            order_side: 0 for BUY, 1 for SELL
            order_amount: Amount in USD from ByBit order
            counterparty_name: Buyer name (SELL) or Seller name (BUY)
            verification_status: NOT_VERIFIED (0) or VERIFIED (1)

        Returns:
            match_id of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO matched_orders (
                    order_id,
                    order_side,
                    order_amount,
                    counterparty_name,
                    matched_at,
                    verification_status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                int(order_side),
                order_amount,
                counterparty_name,
                datetime.now().isoformat(),
                int(verification_status)
            ))

            return cursor.lastrowid

    def add_match(
        self,
        order_id: str,
        order_side: OrderSide,
        order_amount: float,
        counterparty_name: str,
        wise_transfer_reference: str,
        wise_amount: float,
        wise_direction: str,
        verification_source: VerificationSource
    ) -> int:
        """
        Add a new matched order to database (automatically marked as VERIFIED).

        Args:
            order_id: ByBit order ID
            order_side: 0 for BUY, 1 for SELL
            order_amount: Amount in USD from ByBit order
            counterparty_name: Buyer name (SELL) or Seller name (BUY)
            wise_transfer_reference: Wise transfer ID
            wise_amount: Amount from Wise transfer
            wise_direction: 'CREDIT' for incoming, 'DEBIT' for outgoing
            verification_source: Source of verification (1=incoming, 2=outgoing)

        Returns:
            match_id of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO matched_orders (
                    order_id,
                    order_side,
                    order_amount,
                    counterparty_name,
                    wise_transfer_reference,
                    wise_amount,
                    wise_direction,
                    matched_at,
                    verification_source,
                    verification_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                int(order_side),
                order_amount,
                counterparty_name,
                wise_transfer_reference,
                wise_amount,
                wise_direction,
                datetime.now().isoformat(),
                int(verification_source),
                int(VerificationStatus.VERIFIED)
            ))

            return cursor.lastrowid

    def update_order_verification(
        self,
        order_id: str,
        wise_transfer_reference: str,
        wise_amount: float,
        wise_direction: str,
        verification_source: VerificationSource
    ) -> bool:
        """
        Update an existing order to mark it as verified.

        Args:
            order_id: ByBit order ID
            wise_transfer_reference: Wise transfer ID
            wise_amount: Amount from Wise transfer
            wise_direction: 'CREDIT' or 'DEBIT'
            verification_source: Source of verification

        Returns:
            True if updated, False if order not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE matched_orders
                SET wise_transfer_reference = ?,
                    wise_amount = ?,
                    wise_direction = ?,
                    verification_source = ?,
                    verification_status = ?
                WHERE order_id = ?
            """, (
                wise_transfer_reference,
                wise_amount,
                wise_direction,
                int(verification_source),
                int(VerificationStatus.VERIFIED),
                order_id
            ))

            return cursor.rowcount > 0

    def is_order_matched(self, order_id: str) -> bool:
        """Check if an order has already been matched"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM matched_orders WHERE order_id = ? LIMIT 1",
                (order_id,)
            )
            return cursor.fetchone() is not None

    def is_order_verified(self, order_id: str) -> bool:
        """Check if an order has been verified"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT verification_status FROM matched_orders WHERE order_id = ? LIMIT 1",
                (order_id,)
            )
            result = cursor.fetchone()
            return result and result[0] == VerificationStatus.VERIFIED

    def is_transfer_used(self, wise_reference: str) -> bool:
        """Check if a Wise transfer has already been used"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM matched_orders WHERE wise_transfer_reference = ? LIMIT 1",
                (wise_reference,)
            )
            return cursor.fetchone() is not None

    def get_match_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get match details by order ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM matched_orders WHERE order_id = ?",
                (order_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_match_by_wise_reference(self, wise_reference: str) -> Optional[Dict[str, Any]]:
        """Get match details by Wise transfer reference"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM matched_orders WHERE wise_transfer_reference = ?",
                (wise_reference,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_matches(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all matched orders, optionally limited"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM matched_orders ORDER BY matched_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_unverified_orders(self) -> List[Dict[str, Any]]:
        """Get all unverified orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE verification_status = ?
                ORDER BY matched_at DESC
            """, (VerificationStatus.NOT_VERIFIED,))
            return [dict(row) for row in cursor.fetchall()]

    def get_verified_orders(self) -> List[Dict[str, Any]]:
        """Get all verified orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE verification_status = ?
                ORDER BY matched_at DESC
            """, (VerificationStatus.VERIFIED,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_unverified_orders(self) -> int:
        """
        Delete all unverified orders from database.

        Returns:
            Number of deleted records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM matched_orders 
                WHERE verification_status = ?
            """, (VerificationStatus.NOT_VERIFIED,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_matches_by_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get all matches for a specific date.

        Args:
            date: Date string in format 'YYYY-MM-DD'
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE DATE(matched_at) = DATE(?)
                ORDER BY matched_at DESC
            """, (date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_matches_by_side(self, order_side: OrderSide) -> List[Dict[str, Any]]:
        """Get all matches for specific order side (BUY or SELL)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE order_side = ?
                ORDER BY matched_at DESC
            """, (int(order_side),))
            return [dict(row) for row in cursor.fetchall()]

    def get_total_volume(self, order_side: Optional[OrderSide] = None, verified_only: bool = True) -> float:
        """
        Calculate total volume of matched orders.

        Args:
            order_side: Optional filter by order side
            verified_only: If True, only count verified orders
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT SUM(order_amount) FROM matched_orders WHERE 1=1"
            params = []

            if verified_only:
                query += " AND verification_status = ?"
                params.append(VerificationStatus.VERIFIED)

            if order_side is not None:
                query += " AND order_side = ?"
                params.append(int(order_side))

            cursor.execute(query, params)
            result = cursor.fetchone()[0]
            return result if result else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics about matched orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total matches
            cursor.execute("SELECT COUNT(*) FROM matched_orders")
            total_matches = cursor.fetchone()[0]

            # Verified vs unverified
            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE verification_status = ?",
                (VerificationStatus.VERIFIED,)
            )
            verified_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE verification_status = ?",
                (VerificationStatus.NOT_VERIFIED,)
            )
            unverified_count = cursor.fetchone()[0]

            # Buy/Sell counts (verified only)
            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE order_side = ? AND verification_status = ?",
                (OrderSide.BUY, VerificationStatus.VERIFIED)
            )
            buy_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE order_side = ? AND verification_status = ?",
                (OrderSide.SELL, VerificationStatus.VERIFIED)
            )
            sell_count = cursor.fetchone()[0]

            # Volume stats (verified only)
            cursor.execute(
                "SELECT SUM(order_amount) FROM matched_orders WHERE order_side = ? AND verification_status = ?",
                (OrderSide.BUY, VerificationStatus.VERIFIED)
            )
            buy_volume = cursor.fetchone()[0] or 0.0

            cursor.execute(
                "SELECT SUM(order_amount) FROM matched_orders WHERE order_side = ? AND verification_status = ?",
                (OrderSide.SELL, VerificationStatus.VERIFIED)
            )
            sell_volume = cursor.fetchone()[0] or 0.0

            return {
                "total_matches": total_matches,
                "verified_orders": verified_count,
                "unverified_orders": unverified_count,
                "buy_orders": buy_count,
                "sell_orders": sell_count,
                "total_buy_volume": buy_volume,
                "total_sell_volume": sell_volume,
                "net_volume": sell_volume - buy_volume
            }

    def delete_match(self, match_id: int) -> bool:
        """Delete a match by ID (use with caution)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM matched_orders WHERE match_id = ?", (match_id,))
            return cursor.rowcount > 0

    def clear_all_matches(self):
        """Clear all matches from database (use with extreme caution)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM matched_orders")
            conn.commit()

    def delete_old_matches(self, days: int = 30) -> int:
        """
        Delete matches older than specified number of days.

        Args:
            days: Number of days to keep (default: 30)

        Returns:
            Number of deleted records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM matched_orders 
                WHERE matched_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_old_matches_count(self, days: int = 30) -> int:
        """
        Count matches older than specified number of days.
        Useful to check before deleting.

        Args:
            days: Number of days threshold

        Returns:
            Count of old records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM matched_orders 
                WHERE matched_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            return cursor.fetchone()[0]

    def archive_old_matches(self, days: int = 30, archive_db_path: str = "matched_orders_archive.db") -> int:
        """
        Archive old matches to a separate database before deletion.
        This is safer than direct deletion as you keep a backup.

        Args:
            days: Number of days to keep in main database
            archive_db_path: Path to archive database

        Returns:
            Number of archived records
        """
        # Get old matches
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE matched_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            old_matches = cursor.fetchall()

        if not old_matches:
            return 0

        # Create archive database with same structure
        archive_conn = sqlite3.connect(archive_db_path)
        archive_cursor = archive_conn.cursor()

        # Create table in archive if it doesn't exist
        archive_cursor.execute("""
            CREATE TABLE IF NOT EXISTS matched_orders (
                match_id INTEGER PRIMARY KEY,
                order_id TEXT NOT NULL,
                order_side INTEGER NOT NULL,
                order_amount REAL NOT NULL,
                counterparty_name TEXT NOT NULL,
                wise_transfer_reference TEXT NOT NULL,
                wise_amount REAL NOT NULL,
                wise_direction TEXT NOT NULL,
                matched_at TIMESTAMP NOT NULL,
                verification_source INTEGER NOT NULL,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert old matches into archive (skip if already exists)
        archived_count = 0
        for match in old_matches:
            try:
                archive_cursor.execute("""
                    INSERT INTO matched_orders (
                        match_id, order_id, order_side, order_amount,
                        counterparty_name, wise_transfer_reference,
                        wise_amount, wise_direction, matched_at, verification_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, match)
                archived_count += 1
            except sqlite3.IntegrityError:
                # Record already exists in archive, skip it
                pass

        archive_conn.commit()
        archive_conn.close()

        # Now delete from main database (all old matches, even if already archived)
        deleted_count = self.delete_old_matches(days)

        if archived_count > 0 or deleted_count > 0:
            print(f"✅ Archived {archived_count} new records and deleted {deleted_count} from main database")

        return archived_count



# Example usage
if __name__ == "__main__":
    # Initialize database
    db = Database()

    # Example 1: Add unverified order (when order is first created)
    match_id = db.add_order(
        order_id="1992070819939557376",
        order_side=OrderSide.SELL,
        order_amount=500.00,
        counterparty_name="John Doe",
        verification_status=VerificationStatus.NOT_VERIFIED
    )
    print(f"Added unverified order with ID: {match_id}")

    # Example 2: Add verified match (when Wise transfer is confirmed)
    match_id = db.add_match(
        order_id="1992070819939557377",
        order_side=OrderSide.SELL,
        order_amount=500.00,
        counterparty_name="Jane Smith",
        wise_transfer_reference="TRANSFER-123456",
        wise_amount=500.00,
        wise_direction="CREDIT",
        verification_source=VerificationSource.WISE_INCOMING
    )
    print(f"Added verified match with ID: {match_id}")

    # Example 3: Update existing order to verified
    updated = db.update_order_verification(
        order_id="1992070819939557376",
        wise_transfer_reference="TRANSFER-789012",
        wise_amount=500.00,
        wise_direction="CREDIT",
        verification_source=VerificationSource.WISE_INCOMING
    )
    print(f"Updated order verification: {updated}")

    # Check verification status
    print(f"Order verified: {db.is_order_verified('1992070819939557376')}")

    # Get unverified orders
    unverified = db.get_unverified_orders()
    print(f"Unverified orders: {len(unverified)}")

    # Delete all unverified orders (daily cleanup)
    deleted = db.delete_unverified_orders()
    print(f"Deleted {deleted} unverified orders")

    # Get statistics
    stats = db.get_statistics()
    print(f"Statistics: {stats}")