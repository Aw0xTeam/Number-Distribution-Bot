import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

def init_db():
    """Initializes the database by creating necessary tables."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Users table for tracking active numbers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                number TEXT,
                country TEXT,
                assigned_at TEXT
            )
        """)
        # Numbers table for available phone numbers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL UNIQUE,
                country TEXT NOT NULL,
                used INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def get_unused_number(country):
    """Retrieves an unused number for a given country."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT number FROM numbers WHERE country=? AND used=0 LIMIT 1", (country,))
        return cursor.fetchone()

def get_random_unused():
    """Retrieves a random unused number from any country."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT number, country FROM numbers WHERE used=0 ORDER BY RANDOM() LIMIT 1")
        return cursor.fetchone()

def release_number(number):
    """Marks a number as unused again."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE numbers SET used=0 WHERE number=?", (number,))
        conn.commit()

def set_active(user_id, number, country):
    """Sets a number as active for a user."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # First, delete any existing active number for this user
        cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        # Then, assign the new number
        cursor.execute(
            "INSERT INTO users (user_id, number, country, assigned_at) VALUES (?, ?, ?, ?)",
            (user_id, number, country, datetime.now(timezone.utc).isoformat())
        )
        # Mark the number as used
        cursor.execute("UPDATE numbers SET used=1 WHERE number=?", (number,))
        conn.commit()

def get_active(user_id):
    """Gets the active number for a user."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT number, country, assigned_at FROM users WHERE user_id=?", (user_id,))
        return cursor.fetchone()

def add_numbers(country, numbers):
    """Adds a list of numbers to the database for a specific country."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        data = [(line.strip(), country) for line in numbers if line.strip()]
        cursor.executemany("INSERT OR IGNORE INTO numbers (number, country) VALUES (?, ?)", data)
        conn.commit()
        return cursor.rowcount

def delete_numbers(country):
    """Deletes all numbers associated with a specific country."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM numbers WHERE country=?", (country,))
        conn.commit()
        return cursor.rowcount
