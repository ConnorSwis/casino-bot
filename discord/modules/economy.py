import random
import sqlite3
from functools import wraps
from typing import Tuple, List


Entry = Tuple[int, int, int]

class Economy:
    """A wrapper for the economy database"""
    def __init__(self):
        self.open()

    def open(self):
        """Initializes the database"""
        self.conn = sqlite3.connect('economy.db')
        self.cur = self.conn.cursor()
        self.cur.execute("""CREATE TABLE IF NOT EXISTS economy (
            user_id INTEGER NOT NULL PRIMARY KEY,
            money INTEGER NOT NULL DEFAULT 0,
            credits INTEGER NOT NULL DEFAULT 0
        )""")

    def close(self):
        """Safely closes the database"""
        if self.conn:
            self.conn.commit()
            self.cur.close()
            self.conn.close()

    def _commit(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.conn.commit()
            return result
        return wrapper

    def get_entry(self, user_id: int) -> Entry:
        self.cur.execute(
            "SELECT * FROM economy WHERE user_id=:user_id",
            {'user_id': user_id}
        )
        result = self.cur.fetchone()
        if result: return result
        return self.new_entry(user_id)

    @_commit
    def new_entry(self, user_id: int) -> Entry:
        try:
            self.cur.execute(
                "INSERT INTO economy(user_id, money, credits) VALUES(?,?,?)",
                (user_id, 0, 0)
            )
            return self.get_entry(user_id)
        except sqlite3.IntegrityError:
            return self.get_entry(user_id)

    @_commit
    def remove_entry(self, user_id: int) -> None:
        self.cur.execute(
            "DELETE FROM economy WHERE user_id=:user_id",
            {'user_id': user_id}
        )

    @_commit
    def set_money(self, user_id: int, money: int) -> Entry:
        self.cur.execute(
            "UPDATE economy SET money=? WHERE user_id=?",
            (money, user_id)
        )
        return self.get_entry(user_id)

    @_commit
    def set_credits(self, user_id: int, credits: int) -> Entry:
        self.cur.execute(
            "UPDATE economy SET credits=? WHERE user_id=?",
            (credits, user_id)
        )
        return self.get_entry(user_id)

    @_commit
    def add_money(self, user_id: int, money_to_add: int) -> Entry:
        money = self.get_entry(user_id)[1]
        total = money + money_to_add
        if total < 0:
            total = 0
        self.set_money(user_id, total)
        return self.get_entry(user_id)

    @_commit
    def add_credits(self, user_id: int, credits_to_add: int) -> Entry:
        credits = self.get_entry(user_id)[2]
        total = credits + credits_to_add
        if total < 0:
            total = 0
        self.set_credits(user_id, total)
        return self.get_entry(user_id)

    def random_entry(self) -> Entry:
        self.cur.execute("SELECT * FROM economy")
        return random.choice(self.cur.fetchall())

    def top_entries(self, n: int=0) -> List[Entry]:
        self.cur.execute("SELECT * FROM economy ORDER BY money DESC")
        return (self.cur.fetchmany(n) if n else self.cur.fetchall())
