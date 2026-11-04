import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "spendly.db")

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid

        today = date.today()

        def day(d):
            return today.replace(day=d).isoformat()

        expenses = [
            (user_id, 450.00, "Food", day(1), "Weekly groceries"),
            (user_id, 120.00, "Transport", day(4), "Auto rickshaw to office"),
            (user_id, 1850.00, "Bills", day(7), "Electricity bill"),
            (user_id, 600.00, "Health", day(10), "Pharmacy"),
            (user_id, 499.00, "Entertainment", day(13), "Movie tickets"),
            (user_id, 2299.00, "Shopping", day(16), "New shirt"),
            (user_id, 300.00, "Other", day(20), "Birthday gift"),
            (user_id, 280.00, "Food", day(25), "Dinner out"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# Optional inclusive date range, appended to every WHERE user_id = ? query.
# A None bound is open, so with both bounds None this is a no-op. The SQL text
# is constant; the dates are only ever passed as ? parameters.
_DATE_FILTER = "AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)"


def _date_params(date_from, date_to):
    return (date_from, date_from, date_to, date_to)


def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? " + _DATE_FILTER + " "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *_date_params(date_from, date_to), limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_expense_summary(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        params = (user_id, *_date_params(date_from, date_to))
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ? " + _DATE_FILTER,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? " + _DATE_FILTER + " "
            "GROUP BY category ORDER BY SUM(amount) DESC, category LIMIT 1",
            params,
        ).fetchone()
        return {
            "total_spent": float(totals["total"]),
            "transaction_count": int(totals["cnt"]),
            "top_category": top["category"] if top else None,
        }
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category AS name, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? " + _DATE_FILTER + " "
            "GROUP BY category ORDER BY SUM(amount) DESC, category",
            (user_id, *_date_params(date_from, date_to)),
        ).fetchall()
    finally:
        conn.close()
    grand_total = sum(row["total"] for row in rows)
    return [
        {
            "name": row["name"],
            "total": float(row["total"]),
            "percent": round(row["total"] / grand_total * 100) if grand_total else 0,
        }
        for row in rows
    ]
