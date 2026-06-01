# -*- coding: utf-8 -*-
"""System Monitor SQLite Database."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

DB_PATH = Path(__file__).parent.parent / "data" / "system_monitor.db"


def get_db() -> sqlite3.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_type_time ON metrics(metric_type, timestamp);
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);

        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pid INTEGER NOT NULL,
            name TEXT NOT NULL,
            cpu_percent REAL NOT NULL,
            memory_mb REAL NOT NULL,
            num_fds INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_processes_timestamp ON processes(timestamp);
        CREATE INDEX IF NOT EXISTS idx_processes_name ON processes(name);
        CREATE INDEX IF NOT EXISTS idx_processes_ts_name ON processes(timestamp, name);

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def insert_metric(conn: sqlite3.Connection, metric_type: str, name: str, value: float, unit: str) -> None:
    """Insert a metric record."""
    conn.execute(
        "INSERT INTO metrics (timestamp, metric_type, name, value, unit) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), metric_type, name, value, unit)
    )


def insert_process_snapshot(conn: sqlite3.Connection, pid: int, name: str, cpu_percent: float, memory_mb: float, num_fds: int) -> None:
    """Insert a process snapshot."""
    conn.execute(
        "INSERT INTO processes (timestamp, pid, name, cpu_percent, memory_mb, num_fds) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), pid, name, cpu_percent, memory_mb, num_fds)
    )


def query_metrics(
    metric_type: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000
) -> List[dict]:
    """Query metrics of a specific type with optional time range."""
    conn = get_db()
    try:
        query = "SELECT timestamp, name, value, unit FROM metrics WHERE metric_type = ?"
        params: List = [metric_type]

        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def query_process_top(
    metric: str,  # cpu/memory/handle
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 20
) -> List[dict]:
    """Query top N processes by metric type, optionally within time range."""
    conn = get_db()
    try:
        now = datetime.now()
        default_start = (now - timedelta(hours=1)).isoformat()

        if start is None:
            start = default_start
        if end is None:
            end = now.isoformat()

        # Determine sort column
        if metric == "cpu":
            sort_col = "cpu_percent"
        elif metric == "memory":
            sort_col = "memory_mb"
        else:  # handle
            sort_col = "num_fds"

        # Query: get latest snapshot within time range, group by process
        cursor = conn.execute(f"""
            SELECT name, pid, AVG({sort_col}) as avg_value, MAX({sort_col}) as max_value
            FROM processes
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY name, pid
            ORDER BY avg_value DESC
            LIMIT ?
        """, (start, end, limit))

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_config_value(key: str, default: str = None) -> Optional[str]:
    """Get a config value."""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_config_value(key: str, value: str) -> None:
    """Set a config value."""
    conn = get_db()
    try:
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def cleanup_data(before: str) -> Tuple[int, int]:
    """Delete records older than cutoff. Returns (metrics_deleted, processes_deleted)."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM metrics WHERE timestamp < ?", (before,))
        metrics_deleted = cursor.rowcount
        cursor = conn.execute("DELETE FROM processes WHERE timestamp < ?", (before,))
        processes_deleted = cursor.rowcount
        conn.commit()
        return metrics_deleted, processes_deleted
    finally:
        conn.close()


def get_data_stats() -> dict:
    """Get statistics about stored data."""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM metrics")
        metrics_count = cursor.fetchone()["cnt"]
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM processes")
        processes_count = cursor.fetchone()["cnt"]
        cursor = conn.execute("SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest FROM metrics")
        row = cursor.fetchone()
        return {
            "metrics_count": metrics_count,
            "processes_count": processes_count,
            "earliest": row["earliest"],
            "latest": row["latest"],
        }
    finally:
        conn.close()
