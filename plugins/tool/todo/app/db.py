import sqlite3
import time
from pathlib import Path
from typing import Optional

TODO_DB_PATH = Path.home() / ".qwenpaw" / "data" / "todo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id           TEXT PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    session_title TEXT,
    description  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_todos_session_id ON todos(session_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_created_at ON todos(created_at);
"""


def _ensure_db() -> None:
    TODO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TODO_DB_PATH))
    conn.executescript(SCHEMA)
    conn.close()


def get_conn() -> sqlite3.Connection:
    _ensure_db()
    conn = sqlite3.connect(str(TODO_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    _ensure_db()
