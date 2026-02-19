"""SQLite database layer for pingboard URL health checks."""

import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "pingboard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    label TEXT,
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    status_code INTEGER,
    response_time_ms REAL,
    error TEXT,
    checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_checks_url_id_checked_at
    ON checks(url_id, checked_at DESC);
"""


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Create tables and indexes if they don't exist."""
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def add_url(
    url: str,
    label: Optional[str] = None,
    interval_seconds: int = 60,
    db_path: Optional[Path] = None,
) -> int:
    """Insert a URL to monitor. Returns the url row id."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO urls (url, label, interval_seconds) VALUES (?, ?, ?)",
            (url, label, interval_seconds),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        # URL already existed — fetch its id
        row = conn.execute("SELECT id FROM urls WHERE url = ?", (url,)).fetchone()
        return row["id"]
    finally:
        conn.close()


def record_check(
    url_id: int,
    status_code: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    error: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Record the result of a health check. Returns the check row id."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO checks (url_id, status_code, response_time_ms, error) VALUES (?, ?, ?, ?)",
            (url_id, status_code, response_time_ms, error),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_latest_checks(
    url_id: int,
    n: int = 10,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Return the most recent *n* checks for a URL, newest first."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM checks WHERE url_id = ? ORDER BY checked_at DESC, id DESC LIMIT ?",
            (url_id, n),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def prune_old_checks(
    keep: int = 200,
    db_path: Optional[Path] = None,
) -> int:
    """Delete all but the newest *keep* checks per URL. Returns rows deleted."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            DELETE FROM checks
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY url_id ORDER BY checked_at DESC
                    ) AS rn
                    FROM checks
                )
                WHERE rn <= ?
            )
            """,
            (keep,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_all_urls(db_path: Optional[Path] = None) -> list[dict]:
    """Return all monitored URLs."""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM urls ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def load_urls_from_json(
    json_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> list[int]:
    """Seed the database from urls.json. Returns list of url ids."""
    path = json_path or Path(__file__).parent / "urls.json"
    with open(path) as f:
        data = json.load(f)

    ids = []
    default_interval = data.get("interval_seconds", 60)
    for entry in data["urls"]:
        url = entry["url"]
        label = entry.get("label")
        interval = entry.get("interval_seconds", default_interval)
        ids.append(add_url(url, label=label, interval_seconds=interval, db_path=db_path))
    return ids
