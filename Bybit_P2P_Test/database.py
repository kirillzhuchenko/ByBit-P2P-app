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
                           CREATE TABLE IF NOT EXISTS matched_orders
                           (
                               match_id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               order_id
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               order_side
                               INTEGER
                               NOT
                               NULL,
                               order_amount
                               REAL
                               NOT
                               NULL,
                               counterparty_name
                               TEXT
                               NOT
                               NULL,
                               wise_transfer_reference
                               TEXT
                               NOT
                               NULL
                               UNIQUE,
                               wise_amount
                               REAL
                               NOT
                               NULL,
                               wise_direction
                               TEXT
                               NOT
                               NULL,
                               matched_at
                               TIMESTAMP
                               NOT
                               NULL,
                               verification_source
                               INTEGER
                               NOT
                               NULL,
                               CONSTRAINT
                               chk_order_side
                               CHECK (
                               order_side
                               IN
                           (
                               0,
                               1
                           )),
                               CONSTRAINT chk_verification_source CHECK
                           (
                               verification_source
                               IN
                           (
                               1,
                               2
                           )),
                               CONSTRAINT chk_wise_direction CHECK
                           (
                               wise_direction
                               IN
                           (
                               'CREDIT',
                               'DEBIT'
                           ))
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

            conn.commit()

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
        Add a new matched order to database.

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
                           INSERT INTO matched_orders (order_id,
                                                       order_side,
                                                       order_amount,
                                                       counterparty_name,
                                                       wise_transfer_reference,
                                                       wise_amount,
                                                       wise_direction,
                                                       matched_at,
                                                       verification_source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               order_id,
                               int(order_side),
                               order_amount,
                               counterparty_name,
                               wise_transfer_reference,
                               wise_amount,
                               wise_direction,
                               datetime.now().isoformat(),
                               int(verification_source)
                           ))

            return cursor.lastrowid

    def is_order_matched(self, order_id: str) -> bool:
        """Check if an order has already been matched"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM matched_orders WHERE order_id = ? LIMIT 1",
                (order_id,)
            )
            return cursor.fetchone() is not None

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

    def get_matches_by_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get all matches for a specific date.

        Args:
            date: Date string in format 'YYYY-MM-DD'
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT *
                           FROM matched_orders
                           WHERE DATE (matched_at) = DATE (?)
                           ORDER BY matched_at DESC
                           """, (date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_matches_by_side(self, order_side: OrderSide) -> List[Dict[str, Any]]:
        """Get all matches for specific order side (BUY or SELL)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT *
                           FROM matched_orders
                           WHERE order_side = ?
                           ORDER BY matched_at DESC
                           """, (int(order_side),))
            return [dict(row) for row in cursor.fetchall()]

    def get_total_volume(self, order_side: Optional[OrderSide] = None) -> float:
        """
        Calculate total volume of matched orders.

        Args:
            order_side: Optional filter by order side
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if order_side is not None:
                cursor.execute(
                    "SELECT SUM(order_amount) FROM matched_orders WHERE order_side = ?",
                    (int(order_side),)
                )
            else:
                cursor.execute("SELECT SUM(order_amount) FROM matched_orders")
            result = cursor.fetchone()[0]
            return result if result else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics about matched orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total matches
            cursor.execute("SELECT COUNT(*) FROM matched_orders")
            total_matches = cursor.fetchone()[0]

            # Buy/Sell counts
            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE order_side = ?",
                (OrderSide.BUY,)
            )
            buy_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM matched_orders WHERE order_side = ?",
                (OrderSide.SELL,)
            )
            sell_count = cursor.fetchone()[0]

            # Volume stats
            cursor.execute(
                "SELECT SUM(order_amount) FROM matched_orders WHERE order_side = ?",
                (OrderSide.BUY,)
            )
            buy_volume = cursor.fetchone()[0] or 0.0

            cursor.execute(
                "SELECT SUM(order_amount) FROM matched_orders WHERE order_side = ?",
                (OrderSide.SELL,)
            )
            sell_volume = cursor.fetchone()[0] or 0.0

            return {
                "total_matches": total_matches,
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


# Example usage
if __name__ == "__main__":
    # Initialize database
    db = Database()

    # Example: Add a matched SELL order
    match_id = db.add_match(
        order_id="1992070819939557376",
        order_side=OrderSide.SELL,
        order_amount=500.00,
        counterparty_name="John Doe",
        wise_transfer_reference="TRANSFER-123456",
        wise_amount=500.00,
        wise_direction="CREDIT",
        verification_source=VerificationSource.WISE_INCOMING
    )
    print(f"Added match with ID: {match_id}")

    # Check if order is already matched
    print(f"Order matched: {db.is_order_matched('1992070819939557376')}")

    # Check if transfer is already used
    print(f"Transfer used: {db.is_transfer_used('TRANSFER-123456')}")

    # Get statistics
    stats = db.get_statistics()
    print(f"Statistics: {stats}")

    # Get all matches
    matches = db.get_all_matches(limit=10)
    print(f"Recent matches: {len(matches)}")