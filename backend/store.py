"""SQLite storage: the user's tier, AI update count, Stripe orders and the saved plan."""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    tier TEXT NOT NULL DEFAULT 'free',
    updates_used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    stripe_session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    amount_cents INTEGER,
    currency TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plans (
    user_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS update_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    message TEXT NOT NULL,
    parsed_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_user(user_id):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        row = db.execute("SELECT id, tier, updates_used FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


def updates_remaining(user):
    if user["tier"] == "pro":
        return None                      # unlimited
    return max(0, config.FREE_UPDATES - user["updates_used"])


def count_update(user_id):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        db.execute("UPDATE users SET updates_used = updates_used + 1 WHERE id = ?", (user_id,))


def log_update(user_id, message, parsed):
    with connect() as db:
        db.execute("INSERT INTO update_log (user_id, message, parsed_json) VALUES (?, ?, ?)",
                   (user_id, message, json.dumps(parsed)))


def grant_pro(user_id, session_id, amount_cents, currency, status):
    """Idempotent: Stripe may deliver the same webhook more than once."""
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        db.execute("UPDATE users SET tier = 'pro' WHERE id = ?", (user_id,))
        cur = db.execute(
            "INSERT OR IGNORE INTO orders (stripe_session_id, user_id, amount_cents, currency, status) "
            "VALUES (?, ?, ?, ?, ?)", (session_id, user_id, amount_cents, currency, status))
        return cur.rowcount == 1         # True the first time this order is seen


def save_plan(user_id, state):
    with connect() as db:
        db.execute("INSERT INTO plans (user_id, state_json) VALUES (?, ?) "
                   "ON CONFLICT(user_id) DO UPDATE SET state_json = excluded.state_json, "
                   "updated_at = CURRENT_TIMESTAMP", (user_id, json.dumps(state)))


def load_plan(user_id):
    with connect() as db:
        row = db.execute("SELECT state_json FROM plans WHERE user_id = ?", (user_id,)).fetchone()
        return json.loads(row["state_json"]) if row else None
