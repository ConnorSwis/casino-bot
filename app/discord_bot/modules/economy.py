from collections.abc import Callable
import logging
import random
import shutil
import sqlite3
from pathlib import Path
from typing import Tuple, List

from app.config import config

Entry = Tuple[int, int, int]
DATABASE_PATH = Path(config.storage.database_path)
LEGACY_DATABASE_PATH = Path(__file__).resolve().parents[3] / "economy.db"
SCHEMA_VERSION = 2

logger = logging.getLogger(__name__)


def _migration_1_create_economy(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS economy (
        user_id INTEGER NOT NULL PRIMARY KEY,
        money INTEGER NOT NULL DEFAULT 0,
        credits INTEGER NOT NULL DEFAULT 0
    )"""
    )


def _migration_2_add_indexes(cur: sqlite3.Cursor) -> None:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_economy_money ON economy(money DESC)")


MIGRATIONS: dict[int, Callable[[sqlite3.Cursor], None]] = {
    1: _migration_1_create_economy,
    2: _migration_2_add_indexes,
}


class Economy:
    """A wrapper for the economy database"""

    def __init__(self):
        self.open()

    def open(self):
        """Initializes the database"""
        if (
            DATABASE_PATH != LEGACY_DATABASE_PATH
            and not DATABASE_PATH.exists()
            and LEGACY_DATABASE_PATH.exists()
        ):
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_DATABASE_PATH, DATABASE_PATH)
            logger.info(
                "Copied legacy economy database from %s to %s",
                LEGACY_DATABASE_PATH,
                DATABASE_PATH,
            )
        self.conn = sqlite3.connect(str(DATABASE_PATH), timeout=30)
        self.cur = self.conn.cursor()
        self._run_migrations()
        self.conn.commit()

    def _run_migrations(self) -> None:
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )"""
        )
        self.cur.execute(
            "INSERT OR IGNORE INTO schema_version(id, version) VALUES(1, 0)"
        )
        self.cur.execute("SELECT version FROM schema_version WHERE id=1")
        row = self.cur.fetchone()
        current_version = int(row[0]) if row else 0

        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported {SCHEMA_VERSION}."
            )

        for target_version in range(current_version + 1, SCHEMA_VERSION + 1):
            migration = MIGRATIONS.get(target_version)
            if migration is None:
                raise RuntimeError(
                    f"Missing migration for schema version {target_version}."
                )
            migration(self.cur)
            self.cur.execute(
                "UPDATE schema_version SET version=? WHERE id=1",
                (target_version,),
            )
            logger.info("Applied economy database migration version=%s", target_version)

    def close(self):
        """Safely closes the database"""
        if getattr(self, "conn", None):
            self.conn.commit()
            if getattr(self, "cur", None):
                self.cur.close()
            self.conn.close()
            self.cur = None
            self.conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _ensure_entry(self, user_id: int) -> None:
        self.cur.execute(
            "INSERT OR IGNORE INTO economy(user_id, money, credits) VALUES(?, ?, ?)",
            (user_id, 0, 0),
        )

    def _fetch_entry(self, user_id: int) -> Entry:
        self.cur.execute(
            "SELECT user_id, money, credits FROM economy WHERE user_id=?",
            (user_id,),
        )
        result = self.cur.fetchone()
        if result is None:
            raise RuntimeError(f"failed to fetch economy entry for user_id={user_id}")
        return result

    def get_entry(self, user_id: int) -> Entry:
        self._ensure_entry(user_id)
        self.conn.commit()
        return self._fetch_entry(user_id)

    def new_entry(self, user_id: int) -> Entry:
        self._ensure_entry(user_id)
        self.conn.commit()
        return self._fetch_entry(user_id)

    def remove_entry(self, user_id: int) -> None:
        self.cur.execute("DELETE FROM economy WHERE user_id=?", (user_id,))
        self.conn.commit()

    def set_money(self, user_id: int, money: int) -> Entry:
        money = max(0, int(money))
        self._ensure_entry(user_id)
        self.cur.execute(
            "UPDATE economy SET money=? WHERE user_id=?",
            (money, user_id),
        )
        self.conn.commit()
        return self._fetch_entry(user_id)

    def set_credits(self, user_id: int, credits: int) -> Entry:
        credits = max(0, int(credits))
        self._ensure_entry(user_id)
        self.cur.execute(
            "UPDATE economy SET credits=? WHERE user_id=?",
            (credits, user_id),
        )
        self.conn.commit()
        return self._fetch_entry(user_id)

    def add_money(self, user_id: int, money_to_add: int) -> Entry:
        self._ensure_entry(user_id)
        self.cur.execute(
            "UPDATE economy SET money=MAX(0, money + ?) WHERE user_id=?",
            (int(money_to_add), user_id),
        )
        self.conn.commit()
        return self._fetch_entry(user_id)

    def add_credits(self, user_id: int, credits_to_add: int) -> Entry:
        self._ensure_entry(user_id)
        self.cur.execute(
            "UPDATE economy SET credits=MAX(0, credits + ?) WHERE user_id=?",
            (int(credits_to_add), user_id),
        )
        self.conn.commit()
        return self._fetch_entry(user_id)

    def random_entry(self) -> Entry:
        self.cur.execute("SELECT * FROM economy")
        entries = self.cur.fetchall()
        if not entries:
            raise RuntimeError("economy has no entries")
        return random.choice(entries)

    def top_entries(self, n: int = 0) -> List[Entry]:
        self.cur.execute("SELECT * FROM economy ORDER BY money DESC")
        return (self.cur.fetchmany(n) if n else self.cur.fetchall())
