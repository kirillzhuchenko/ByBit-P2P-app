"""
Database module for tracking matched orders between ByBit P2P and Wise transfers.
Stores verification data and messaging status to prevent double-matching and maintain audit trail.
"""

import sqlite3
from datetime import datetime, timedelta
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
    FRAUD_DETECTED = 2


class Database:
    """Database handler for matched order tracking with messaging support"""

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
        """Initialize database schema with messaging tracking"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create matched_orders table with messaging fields
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
                    message_sent BOOLEAN DEFAULT 0,
                    message_sent_at TIMESTAMP,
                    message_retry_count INTEGER DEFAULT 0,
                    CONSTRAINT chk_order_side CHECK (order_side IN (0, 1)),
                    CONSTRAINT chk_verification_source CHECK (verification_source IN (1, 2) OR verification_source IS NULL),
                    CONSTRAINT chk_wise_direction CHECK (wise_direction IN ('CREDIT', 'DEBIT') OR wise_direction IS NULL),
                    CONSTRAINT chk_verification_status CHECK (verification_status IN (0, 1, 2))
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

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_sent 
                ON matched_orders(message_sent)
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

    # =========================================================================
    # MESSAGING METHODS
    # =========================================================================

    def mark_order_messaged(self, order_id: str, retry_count: int = 0) -> bool:
        """
        Mark that payment instructions have been sent for this order.

        Args:
            order_id: The order ID
            retry_count: Number of times message sending was attempted

        Returns:
            True if updated, False if order not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE matched_orders 
                SET message_sent = 1, 
                    message_sent_at = ?,
                    message_retry_count = ?
                WHERE order_id = ?
            """, (datetime.now().isoformat(), retry_count, order_id))
            return cursor.rowcount > 0

    def was_order_messaged(self, order_id: str) -> bool:
        """
        Check if payment instructions were already sent for this order.

        Returns:
            True if message was sent, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_sent FROM matched_orders WHERE order_id = ?
            """, (order_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False

    def get_unmessaged_orders(self, order_side: Optional[OrderSide] = None) -> List[Dict[str, Any]]:
        """
        Get all orders that haven't been messaged yet.

        Args:
            order_side: Filter by order side (0=BUY, 1=SELL). None returns all.

        Returns:
            List of unmessaged orders
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if order_side is not None:
                query = """
                    SELECT order_id, order_side, order_amount, counterparty_name, matched_at
                    FROM matched_orders 
                    WHERE message_sent = 0 AND order_side = ?
                    ORDER BY matched_at ASC
                """
                cursor.execute(query, (int(order_side),))
            else:
                query = """
                    SELECT order_id, order_side, order_amount, counterparty_name, matched_at
                    FROM matched_orders 
                    WHERE message_sent = 0
                    ORDER BY matched_at ASC
                """
                cursor.execute(query)

            return [dict(row) for row in cursor.fetchall()]

    def get_messaging_statistics(self) -> Dict[str, Any]:
        """Get statistics about messaging status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN message_sent = 1 THEN 1 ELSE 0 END) as messaged,
                    SUM(CASE WHEN message_sent = 0 THEN 1 ELSE 0 END) as unmessaged,
                    AVG(message_retry_count) as avg_retries
                FROM matched_orders
                WHERE order_side = 1  -- SELL orders only
            """)
            row = cursor.fetchone()
            return {
                'total_sell_orders': row[0] or 0,
                'messaged': row[1] or 0,
                'unmessaged': row[2] or 0,
                'avg_retries': round(row[3] or 0, 2)
            }

    def reset_message_status(self, order_id: str) -> bool:
        """
        Reset message status for an order (useful for re-sending).
        Use with caution - may cause duplicate messages.

        Returns:
            True if updated, False if order not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE matched_orders 
                SET message_sent = 0,
                    message_sent_at = NULL
                WHERE order_id = ?
            """, (order_id,))
            return cursor.rowcount > 0

    def get_orders_messaged_in_last_hours(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get orders that were messaged in the last N hours."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id, counterparty_name, order_amount, message_sent_at
                FROM matched_orders
                WHERE message_sent = 1 AND message_sent_at > ?
                ORDER BY message_sent_at DESC
            """, (cutoff,))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # EXISTING METHODS (unchanged)
    # =========================================================================

    def is_order_matched(self, order_id: str) -> bool:
        """Check if an order has already been matched"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM matched_orders WHERE order_id = ? LIMIT 1",
                (order_id,)
            )
            return cursor.fetchone() is not None

    def mark_order_as_fraud(self, order_id: str) -> bool:
        """
        Mark an order as fraud detected.

        Args:
            order_id: ByBit order ID

        Returns:
            True if updated, False if order not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE matched_orders
                SET verification_status = ?
                WHERE order_id = ?
            """, (
                int(VerificationStatus.FRAUD_DETECTED),
                order_id
            ))

            return cursor.rowcount > 0

    def override_fraud_and_verify(
        self,
        order_id: str,
        wise_transfer_reference: str,
        wise_amount: float,
        wise_direction: str,
        verification_source: VerificationSource
    ) -> bool:
        """
        Override fraud status and mark order as verified when legitimate payment is found.
        This handles cases where an order was initially flagged as fraud but later
        a valid matching transfer is discovered.

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

    def get_fraud_orders(self) -> List[Dict[str, Any]]:
        """Get all orders marked as fraud"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matched_orders 
                WHERE verification_status = ?
                ORDER BY matched_at DESC
            """, (VerificationStatus.FRAUD_DETECTED,))
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

            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE verification_status = ?",
                (VerificationStatus.FRAUD_DETECTED,)
            )
            fraud_count = cursor.fetchone()[0]

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
                "fraud_orders": fraud_count,
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
                wise_transfer_reference TEXT,
                wise_amount REAL,
                wise_direction TEXT,
                matched_at TIMESTAMP NOT NULL,
                verification_source INTEGER,
                verification_status INTEGER NOT NULL,
                message_sent BOOLEAN,
                message_sent_at TIMESTAMP,
                message_retry_count INTEGER,
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
                        wise_amount, wise_direction, matched_at, verification_source,
                        verification_status, message_sent, message_sent_at, message_retry_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(match))
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

    # Example 2: Mark order as messaged
    db.mark_order_messaged("1992070819939557376", retry_count=0)
    print(f"Marked order as messaged")

    # Example 3: Check if messaged
    was_messaged = db.was_order_messaged("1992070819939557376")
    print(f"Order was messaged: {was_messaged}")

    # Example 4: Get unmessaged orders
    unmessaged = db.get_unmessaged_orders(order_side=OrderSide.SELL)
    print(f"Unmessaged SELL orders: {len(unmessaged)}")

    # Example 5: Get messaging statistics
    msg_stats = db.get_messaging_statistics()
    print(f"Messaging stats: {msg_stats}")

    # Example 6: Update to verified
    updated = db.update_order_verification(
        order_id="1992070819939557376",
        wise_transfer_reference="TRANSFER-789012",
        wise_amount=500.00,
        wise_direction="CREDIT",
        verification_source=VerificationSource.WISE_INCOMING
    )
    print(f"Updated order verification: {updated}")

    # Get statistics
    stats = db.get_statistics()
    print(f"Statistics: {stats}")