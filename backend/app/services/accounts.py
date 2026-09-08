"""Local SQLite accounts, opaque sessions and explicitly published event snapshots."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@contextmanager
def database():
    path = Path(os.environ.get("HEUNGMAP_DB_PATH", str(Path(__file__).resolve().parents[3] / "data" / "heungmap.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
                name TEXT NOT NULL, role TEXT, UNIQUE(provider, subject)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oauth_transactions (
                token_hash TEXT PRIMARY KEY, state TEXT NOT NULL, nonce TEXT NOT NULL,
                verifier TEXT NOT NULL, expires REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS publications (
                event_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, event_json TEXT NOT NULL,
                prediction_json TEXT NOT NULL, nearby_json TEXT NOT NULL
            );
        """)
        yield connection
        connection.commit()
    finally:
        connection.close()


def identity(provider: str, subject: str, name: str) -> dict:
    with database() as db:
        db.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, NULL)",
                   ("usr_" + secrets.token_hex(16), provider, subject, name[:100]))
        db.execute("UPDATE users SET name=? WHERE provider=? AND subject=?", (name[:100], provider, subject))
        return dict(db.execute("SELECT id, name, role, provider FROM users WHERE provider=? AND subject=?",
                               (provider, subject)).fetchone())


def issue_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with database() as db:
        db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (digest(token), user_id, time.time() + 86400 * 7))
    return token


def session_user(token: str | None) -> dict | None:
    if not token:
        return None
    with database() as db:
        row = db.execute("""SELECT u.id, u.name, u.role, u.provider FROM users u
            JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires>?""",
                         (digest(token), time.time())).fetchone()
        return dict(row) if row else None


def revoke(token: str | None):
    if token:
        with database() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (digest(token),))
