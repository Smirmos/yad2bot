import sqlite3
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "seen_listings.db") -> None:
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_listings (
                listing_id TEXT PRIMARY KEY,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def is_seen(self, listing_id: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM seen_listings WHERE listing_id = ?", (str(listing_id),)
        )
        return cursor.fetchone() is not None

    def mark_seen(self, listing_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_listings (listing_id) VALUES (?)",
            (str(listing_id),),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
