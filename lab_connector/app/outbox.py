from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class Outbox:
    """SQLite-backed durable queue for POST bodies."""

    def __init__(self, db_path: Path, backoff_sec: list[int]) -> None:
        self._db_path = db_path
        self._backoff = backoff_sec or [60]
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox (status, next_retry_at, id)")

    def enqueue(self, body: bytes) -> int:
        with self._lock, self._connect() as c:
            cur = c.execute(
                "INSERT INTO outbox (body, status, created_at) VALUES (?, 'pending', ?)",
                (body.decode("utf-8"), _utc_now_iso()),
            )
            c.commit()
            return int(cur.lastrowid)

    def fetch_pending(self, limit: int = 20) -> list[sqlite3.Row]:
        now = _utc_now_iso()
        with self._lock, self._connect() as c:
            return list(
                c.execute(
                    """
                    SELECT id, body, attempts, status
                    FROM outbox
                    WHERE status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?)
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (now, limit),
                ).fetchall()
            )

    def mark_delivered(self, row_id: int) -> None:
        with self._lock, self._connect() as c:
            c.execute("UPDATE outbox SET status = 'delivered' WHERE id = ?", (row_id,))
            c.commit()

    def mark_retry(self, row_id: int, attempts_before: int, err: str) -> None:
        idx = min(attempts_before, len(self._backoff) - 1)
        delay = self._backoff[idx]
        nxt = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        with self._lock, self._connect() as c:
            c.execute(
                """
                UPDATE outbox
                SET attempts = attempts + 1, next_retry_at = ?, last_error = ?
                WHERE id = ?
                """,
                (nxt, err[:2000], row_id),
            )
            c.commit()

    def mark_dead(self, row_id: int, err: str) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                "UPDATE outbox SET status = 'dead', last_error = ? WHERE id = ?",
                (err[:2000], row_id),
            )
            c.commit()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def body_json(row: sqlite3.Row) -> dict[str, Any]:
    return json.loads(row["body"])
