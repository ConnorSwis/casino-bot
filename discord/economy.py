import random
import sqlite3
from functools import wraps
from typing import Tuple


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
            money INTEGER NOT NULL
        )""")
        

    def close(self):
        """Safely closes the database"""
        if self.conn:
            self.conn.commit()
            self.cur.close()
            self.conn.close()

    def _commit(func):
        """Runs the function and commits the database

        Args:
            func (function): The function to be decorated

        Returns:
            function: The decorated function
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.conn.commit()
            return result
        return wrapper

    def get_entry(self, user_id: int) -> Tuple[int, int]:
        """Fetches entry by ID. Creates one if it doesn't already exist.

        Args:
            user_id (int): The ID of the user

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        self.cur.execute("SELECT * FROM economy WHERE user_id=:user_id", {'user_id': user_id})
        if result:=self.cur.fetchone():
            return result
        return self.new_entry(user_id)

    @_commit
    def new_entry(self, user_id: int) -> Tuple[int, int]:
        """Creates a new entry in the database with 0 money

        Args:
            user_id (int): The ID of the user

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        try:
            self.cur.execute("INSERT INTO economy(user_id, money) VALUES(?,?)", (user_id, 0))
            return self.get_entry(user_id)
        except sqlite3.IntegrityError:
            return self.get_entry(user_id)

    @_commit
    def remove_entry(self, user_id: int) -> None:
        """Removes entry by user ID

        Args:
            user_id (int): The ID of the user
        """
        self.cur.execute("DELETE FROM economy WHERE user_id=:user_id", {'user_id': user_id})

    @_commit
    def set_money(self, user_id: int, money: int) -> Tuple[int, int]:
        """Set the amount of money a user has

        Args:
            user_id (int): The ID of the user
            money (int): The amount of money to set to

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        self.cur.execute("UPDATE economy SET money=? WHERE user_id=?", (money, user_id))
        return self.get_entry(user_id)

    @_commit
    def add_money(self, user_id: int, money_to_add: int) -> Tuple[int, int]:
        """Adds money to user's money; can be negative

        Args:
            user_id (int): The ID of the user
            money_to_add (int): The amount of money to add; can be negative

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        money = self.get_entry(user_id)[1]
        if (total:=money+money_to_add) < 0:
            total = 0
        self.set_money(user_id, total)
        return self.get_entry(user_id)

    def random_entry(self) -> Tuple[int, int]:
        """Gives a random entry in the database

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        self.cur.execute("SELECT * FROM economy")
        return random.choice(self.cur.fetchall())

    def top_entry(self) -> Tuple[int, int]:
        """Fetches the entry with the most money

        Returns:
            Tuple[int, int]: The ID of the user and their money
        """
        self.cur.execute("SELECT * FROM economy ORDER BY money DESC LIMIT 1")
        return self.cur.fetchone()

