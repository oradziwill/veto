from __future__ import annotations

import sqlite3
from pathlib import Path


class AgentStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
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
                CREATE TABLE IF NOT EXISTS processed_commands (
                    command_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL,
                    fiscal_number TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            c.commit()

    def get_processed(self, command_id: int) -> sqlite3.Row | None:
        with self._connect() as c:
            return c.execute(
                "SELECT command_id, status, fiscal_number FROM processed_commands WHERE command_id = ?",
                (command_id,),
            ).fetchone()

    def upsert_processed(self, command_id: int, status: str, fiscal_number: str = "") -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO processed_commands (command_id, status, fiscal_number)
                VALUES (?, ?, ?)
                ON CONFLICT(command_id) DO UPDATE SET
                    status=excluded.status,
                    fiscal_number=excluded.fiscal_number,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (command_id, status, fiscal_number),
            )
            c.commit()
