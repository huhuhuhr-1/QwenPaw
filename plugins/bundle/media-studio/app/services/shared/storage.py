import asyncio
import uuid
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from abc import ABC, abstractmethod

import aiosqlite

from app.config import settings


class FileStorage(ABC):
    @abstractmethod
    async def save(self, file_id: str, original_name: str, content: bytes) -> Path:
        ...

    @abstractmethod
    async def read(self, file_id: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, file_id: str) -> None:
        ...

    @abstractmethod
    async def get_path(self, file_id: str) -> Path:
        ...


class LocalStorage(FileStorage):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    async def save(self, file_id: str, original_name: str, content: bytes) -> Path:
        d = self.base_dir / file_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / original_name
        p.write_bytes(content)
        return p

    async def read(self, file_id: str) -> bytes:
        d = self.base_dir / file_id
        if not d.exists():
            raise FileNotFoundError(f"file {file_id} not found")
        items = list(d.iterdir())
        if not items:
            raise FileNotFoundError(f"file {file_id} dir is empty")
        return items[0].read_bytes()

    async def get_path(self, file_id: str) -> Path:
        d = self.base_dir / file_id
        if not d.exists():
            raise FileNotFoundError(f"file {file_id} not found")
        items = list(d.iterdir())
        if not items:
            raise FileNotFoundError(f"file {file_id} dir is empty")
        return items[0]

    async def delete(self, file_id: str) -> None:
        d = self.base_dir / file_id
        if d.exists():
            import shutil
            shutil.rmtree(d)

    def get_filename(self, file_id: str) -> Optional[str]:
        d = self.base_dir / file_id
        if not d.exists():
            return None
        items = list(d.iterdir())
        return items[0].name if items else None


SCHEMA_VERSION = 3


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path, timeout=30.0)
        self._conn.row_factory = aiosqlite.Row
        async with self._lock:
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._conn.execute("PRAGMA busy_timeout=30000")
            await self._conn.commit()
        await self._ensure_schema()

    async def _fetchone(self, sql: str, params=()):
        async with self._lock:
            cur = await self._conn.execute(sql, params)
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params=()):
        async with self._lock:
            cur = await self._conn.execute(sql, params)
            return await cur.fetchall()

    async def _execute_commit(self, sql: str, params=()):
        async with self._lock:
            await self._conn.execute(sql, params)
            await self._conn.commit()

    async def _run_writes(
        self, fn: Callable[[aiosqlite.Connection], Awaitable[None]]
    ) -> None:
        async with self._lock:
            await fn(self._conn)
            await self._conn.commit()

    async def _ensure_schema(self):
        async with self._lock:
            await self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            cur = await self._conn.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            )
            row = await cur.fetchone()
            current = int(row[0]) if row else 0
            await self._create_tables_unlocked()
            await self._migrate_steps_run_model_unlocked()
            if current != SCHEMA_VERSION:
                await self._conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            await self._conn.commit()

    async def _migrate_steps_run_model_unlocked(self) -> None:
        cur = await self._conn.execute("PRAGMA table_info(steps)")
        cols = {row[1] for row in await cur.fetchall()}
        if "run_model" not in cols:
            await self._conn.execute("ALTER TABLE steps ADD COLUMN run_model TEXT")

    async def _create_tables_unlocked(self):
        await self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id            TEXT PRIMARY KEY,
            file_type     TEXT NOT NULL,
            original_name TEXT NOT NULL,
            stored_path   TEXT NOT NULL,
            size_bytes    INTEGER DEFAULT 0,
            mime_type     TEXT,
            file_hash     TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id              TEXT PRIMARY KEY,
            name            TEXT,
            entry_file_id   TEXT NOT NULL,
            entry_type      TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            transcribe_lane TEXT NOT NULL DEFAULT 'fast',
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entry_file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS steps (
            id             TEXT PRIMARY KEY,
            workflow_id    TEXT NOT NULL,
            step_type      TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'pending',
            input_file_id  TEXT,
            output_file_id TEXT,
            depends_on     TEXT,
            error          TEXT,
            run_model      TEXT,
            started_at     TEXT,
            completed_at   TEXT,
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (workflow_id) REFERENCES workflows(id),
            FOREIGN KEY (input_file_id) REFERENCES files(id),
            FOREIGN KEY (output_file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS step_logs (
            id         TEXT PRIMARY KEY,
            step_id    TEXT,
            level      TEXT NOT NULL DEFAULT 'INFO',
            message    TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (step_id) REFERENCES steps(id)
        );

        CREATE INDEX IF NOT EXISTS idx_step_logs_step ON step_logs(step_id);
        CREATE INDEX IF NOT EXISTS idx_step_logs_created ON step_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_steps_workflow ON steps(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_steps_status ON steps(status);
        CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
        """)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- File CRUD ---

    async def create_file(self, file_id: str, file_type: str, original_name: str,
                          stored_path: str, size_bytes: int = 0, mime_type: str = "",
                          file_hash: str = "") -> dict:
        await self._execute_commit(
            "INSERT INTO files (id, file_type, original_name, stored_path, size_bytes, mime_type, file_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, file_type, original_name, stored_path, size_bytes, mime_type, file_hash),
        )
        return await self.get_file(file_id)
    async def get_file(self, file_id: str) -> Optional[dict]:
        row = await self._fetchone("SELECT * FROM files WHERE id=?", (file_id,))
        return dict(row) if row else None

    async def update_file_size(self, file_id: str, size: int):
        await self._execute_commit(
            "UPDATE files SET size_bytes=? WHERE id=?", (size, file_id)
        )

    async def update_file_path(self, file_id: str, path: str):
        await self._execute_commit(
            "UPDATE files SET stored_path=? WHERE id=?", (path, file_id)
        )

    # --- Workflow CRUD ---

    async def create_workflow(
        self,
        wf_id: str,
        entry_file_id: str,
        entry_type: str,
        name: Optional[str] = None,
        *,
        transcribe_lane: str = "fast",
    ) -> dict:
        now = self._now()
        await self._execute_commit(
            "INSERT INTO workflows "
            "(id, name, entry_file_id, entry_type, status, transcribe_lane, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (wf_id, name, entry_file_id, entry_type, "pending", transcribe_lane, now, now),
        )
        wf = await self.get_workflow(wf_id)
        await self.add_log(None, "INFO", f"workflow created, entry_type={entry_type}")
        return wf

    async def get_workflow(self, wf_id: str) -> Optional[dict]:
        row = await self._fetchone("SELECT * FROM workflows WHERE id=?", (wf_id,))
        return dict(row) if row else None

    async def count_workflows(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) AS n FROM workflows")
        return int(row["n"]) if row else 0

    async def list_workflows(self, *, offset: int = 0, limit: int | None = None) -> list[dict]:
        if limit is None:
            rows = await self._fetchall(
                "SELECT * FROM workflows ORDER BY created_at DESC, id DESC"
            )
        else:
            rows = await self._fetchall(
                "SELECT * FROM workflows ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [dict(r) for r in rows]

    async def update_workflow_status(self, wf_id: str, status: str, error: Optional[str] = None):
        now = self._now()
        await self._execute_commit(
            "UPDATE workflows SET status=?, updated_at=? WHERE id=?",
            (status, now, wf_id),
        )

    async def update_workflow_transcribe_lane(self, wf_id: str, lane: str) -> None:
        now = self._now()
        await self._execute_commit(
            "UPDATE workflows SET transcribe_lane=?, updated_at=? WHERE id=?",
            (lane, now, wf_id),
        )

    async def get_active_workflows(self) -> list[dict]:
        rows = await self._fetchall(
            "SELECT * FROM workflows WHERE status IN ('pending','processing','paused')"
        )
        return [dict(r) for r in rows]

    # --- Step CRUD ---

    async def create_step(self, step_id: str, workflow_id: str, step_type: str,
                          input_file_id: str, depends_on: Optional[str] = None) -> dict:
        await self._execute_commit(
            "INSERT INTO steps (id, workflow_id, step_type, status, input_file_id, depends_on) "
            "VALUES (?,?,?,?,?,?)",
            (step_id, workflow_id, step_type, "pending", input_file_id, depends_on),
        )
        return await self.get_step(step_id)

    async def get_step(self, step_id: str) -> Optional[dict]:
        row = await self._fetchone("SELECT * FROM steps WHERE id=?", (step_id,))
        return dict(row) if row else None

    async def get_workflow_steps(self, workflow_id: str) -> list[dict]:
        rows = await self._fetchall(
            "SELECT * FROM steps WHERE workflow_id=? ORDER BY created_at", (workflow_id,)
        )
        return [dict(r) for r in rows]

    async def update_step(self, step_id: str, **kwargs):
        sets = []
        vals = []
        for k, v in kwargs.items():
            sets.append(f"{k}=?")
            vals.append(v)
        now = self._now()
        sets.append("updated_at=?")
        vals.append(now)
        vals.append(step_id)
        await self._execute_commit(
            f"UPDATE steps SET {','.join(sets)} WHERE id=?", tuple(vals)
        )

    async def get_pending_dependents(self, workflow_id: str, completed_step_id: str) -> list[dict]:
        rows = await self._fetchall("SELECT * FROM steps WHERE workflow_id=? AND depends_on=? AND status='pending'",             (workflow_id, completed_step_id))
        return [dict(r) for r in rows]

    async def get_steps_by_status(self, status: str) -> list[dict]:
        rows = await self._fetchall("SELECT * FROM steps WHERE status=?", (status,))
        return [dict(r) for r in rows]

    async def count_steps_by_type_and_status(self) -> list[dict]:
        rows = await self._fetchall("""             SELECT step_type, status, COUNT(*) AS count             FROM steps             WHERE step_type IN ('extract_audio', 'transcribe', 'polish')             GROUP BY step_type, status             """)
        return [dict(r) for r in rows]

    async def count_runnable_pending_by_type(self) -> list[dict]:
        """Pending steps whose dependencies are satisfied (queued for workers)."""
        rows = await self._fetchall("""             SELECT s.step_type, COUNT(*) AS count             FROM steps s             LEFT JOIN steps dep ON s.depends_on = dep.id             WHERE s.status = 'pending'               AND s.step_type IN ('extract_audio', 'transcribe', 'polish')               AND (s.depends_on IS NULL OR dep.status = 'completed')             GROUP BY s.step_type             """)
        return [dict(r) for r in rows]

    async def count_waiting_deps_pending_by_type(self) -> list[dict]:
        rows = await self._fetchall("""             SELECT s.step_type, COUNT(*) AS count             FROM steps s             INNER JOIN steps dep ON s.depends_on = dep.id             WHERE s.status = 'pending'               AND s.step_type IN ('extract_audio', 'transcribe', 'polish')               AND dep.status != 'completed'             GROUP BY s.step_type             """)
        return [dict(r) for r in rows]

    async def get_runnable_pending_steps(
        self,
        *,
        step_type: str | None = None,
        workflow_id: str | None = None,
        transcribe_lane: str | None = None,
    ) -> list[dict]:
        sql = """
            SELECT s.*, w.transcribe_lane AS transcribe_lane
            FROM steps s
            LEFT JOIN steps dep ON s.depends_on = dep.id
            INNER JOIN workflows w ON s.workflow_id = w.id
            WHERE s.status = 'pending'
              AND w.status = 'processing'
              AND (s.depends_on IS NULL OR dep.status = 'completed')
        """
        params: list = []
        if step_type:
            sql += " AND s.step_type = ?"
            params.append(step_type)
        if workflow_id:
            sql += " AND s.workflow_id = ?"
            params.append(workflow_id)
        if transcribe_lane is not None:
            sql += " AND w.transcribe_lane = ?"
            params.append(transcribe_lane)
        sql += " ORDER BY w.created_at ASC, s.id ASC"
        rows = await self._fetchall(sql, params)
        return [dict(r) for r in rows]

    async def count_transcribe_by_lane_and_status(self) -> list[dict]:
        rows = await self._fetchall("""             SELECT COALESCE(w.transcribe_lane, 'fast') AS transcribe_lane,                    s.status,                    COUNT(*) AS count             FROM steps s             INNER JOIN workflows w ON s.workflow_id = w.id             WHERE s.step_type = 'transcribe'             GROUP BY transcribe_lane, s.status             """)
        return [dict(r) for r in rows]

    async def count_runnable_pending_transcribe_by_lane(self) -> list[dict]:
        rows = await self._fetchall("""             SELECT COALESCE(w.transcribe_lane, 'fast') AS transcribe_lane,                    COUNT(*) AS count             FROM steps s             LEFT JOIN steps dep ON s.depends_on = dep.id             INNER JOIN workflows w ON s.workflow_id = w.id             WHERE s.status = 'pending'               AND s.step_type = 'transcribe'               AND w.status = 'processing'               AND (s.depends_on IS NULL OR dep.status = 'completed')             GROUP BY transcribe_lane             """)
        return [dict(r) for r in rows]

    async def count_waiting_deps_transcribe_by_lane(self) -> list[dict]:
        rows = await self._fetchall("""             SELECT COALESCE(w.transcribe_lane, 'fast') AS transcribe_lane,                    COUNT(*) AS count             FROM steps s             INNER JOIN steps dep ON s.depends_on = dep.id             INNER JOIN workflows w ON s.workflow_id = w.id             WHERE s.status = 'pending'               AND s.step_type = 'transcribe'               AND dep.status != 'completed'             GROUP BY transcribe_lane             """)
        return [dict(r) for r in rows]

    async def get_cascade_failed(self, workflow_id: str, failed_step_id: str) -> list[dict]:
        rows = await self._fetchall("SELECT * FROM steps WHERE workflow_id=? AND depends_on=? AND status='failed'",             (workflow_id, failed_step_id))
        return [dict(r) for r in rows]

    async def get_steps_by_depends_on(self, workflow_id: str, depends_on: str) -> list[dict]:
        rows = await self._fetchall("SELECT * FROM steps WHERE workflow_id=? AND depends_on=?",             (workflow_id, depends_on))
        return [dict(r) for r in rows]

    # --- Logs ---

    async def add_log(self, step_id: Optional[str], level: str, message: str):
        log_id = uuid.uuid4().hex[:12]
        await self._execute_commit("INSERT INTO step_logs (id, step_id, level, message) VALUES (?,?,?,?)",             (log_id, step_id, level, message))

    async def get_step_logs(self, step_id: str) -> list[dict]:
        rows = await self._fetchall("SELECT * FROM step_logs WHERE step_id=? ORDER BY created_at", (step_id,))
        return [dict(r) for r in rows]

    async def file_is_orphan(self, file_id: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM workflows WHERE entry_file_id=? LIMIT 1", (file_id,)
        )
        if row:
            return False
        row = await self._fetchone(
            "SELECT 1 FROM steps WHERE input_file_id=? OR output_file_id=? LIMIT 1",
            (file_id, file_id),
        )
        return row is None

    async def delete_file_record(self, file_id: str) -> None:
        await self._execute_commit("DELETE FROM files WHERE id=?", (file_id,))

    async def delete_workflow_record(self, workflow_id: str) -> None:
        steps = await self.get_workflow_steps(workflow_id)
        step_ids = [s["id"] for s in steps]

        async def _delete(conn: aiosqlite.Connection) -> None:
            if step_ids:
                placeholders = ",".join("?" * len(step_ids))
                await conn.execute(
                    f"DELETE FROM step_logs WHERE step_id IN ({placeholders})",
                    step_ids,
                )
            await conn.execute("DELETE FROM steps WHERE workflow_id=?", (workflow_id,))
            await conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))

        await self._run_writes(_delete)

    _ARTIFACT_SELECT = """
        SELECT
            f.id AS file_id,
            f.original_name,
            f.file_type,
            f.size_bytes,
            s.step_type,
            s.started_at,
            s.completed_at,
            s.run_model,
            s.workflow_id,
            s.id AS step_id,
            w.transcribe_lane,
            entry.original_name AS source_name,
            w.created_at AS workflow_created_at
        FROM steps s
        INNER JOIN files f ON s.output_file_id = f.id
        INNER JOIN workflows w ON s.workflow_id = w.id
        INNER JOIN files entry ON w.entry_file_id = entry.id
        WHERE s.status = 'completed' AND s.output_file_id IS NOT NULL
    """

    async def count_artifacts(self, *, step_type: str | None = None) -> int:
        sql = (
            "SELECT COUNT(*) AS n FROM steps s "
            "WHERE s.status = 'completed' AND s.output_file_id IS NOT NULL"
        )
        params: list = []
        if step_type:
            sql += " AND s.step_type = ?"
            params.append(step_type)
        row = await self._fetchone(sql, params)
        return int(row["n"]) if row else 0

    async def list_artifacts(
        self, *, offset: int = 0, limit: int = 20, step_type: str | None = None
    ) -> list[dict]:
        sql = self._ARTIFACT_SELECT
        params: list = []
        if step_type:
            sql += " AND s.step_type = ?"
            params.append(step_type)
        sql += " ORDER BY s.completed_at DESC, f.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = await self._fetchall(sql, params)
        return [dict(r) for r in rows]

    async def get_artifact_by_file_id(self, file_id: str) -> Optional[dict]:
        row = await self._fetchone(self._ARTIFACT_SELECT + " AND s.output_file_id = ?",             (file_id,),)
        return dict(row) if row else None

    async def get_workflow_logs(self, workflow_id: str) -> list[dict]:
        rows = await self._fetchall("""             SELECT l.id, l.step_id, l.level, l.message, l.created_at, s.step_type             FROM step_logs l             JOIN steps s ON l.step_id = s.id             WHERE s.workflow_id=?             ORDER BY l.created_at             """,             (workflow_id,),)
        return [dict(r) for r in rows]

    _GLOBAL_LOG_FROM = """
        FROM step_logs l
        LEFT JOIN steps s ON l.step_id = s.id
        LEFT JOIN workflows w ON s.workflow_id = w.id
        LEFT JOIN files entry ON w.entry_file_id = entry.id
    """

    def _global_log_where(
        self, *, level: str | None = None, workflow_id: str | None = None
    ) -> tuple[str, list]:
        clauses: list[str] = []
        params: list = []
        if level:
            clauses.append("l.level = ?")
            params.append(level.upper())
        if workflow_id:
            clauses.append("s.workflow_id = ?")
            params.append(workflow_id)
        if not clauses:
            return "", params
        return " WHERE " + " AND ".join(clauses), params

    async def count_global_logs(
        self, *, level: str | None = None, workflow_id: str | None = None
    ) -> int:
        where, params = self._global_log_where(level=level, workflow_id=workflow_id)
        row = await self._fetchone(f"SELECT COUNT(*) AS n {self._GLOBAL_LOG_FROM}{where}",             params,)
        return int(row["n"]) if row else 0

    async def list_global_logs(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        level: str | None = None,
        workflow_id: str | None = None,
    ) -> list[dict]:
        where, params = self._global_log_where(level=level, workflow_id=workflow_id)
        rows = await self._fetchall(f"""             SELECT                 l.id,                 l.step_id,                 l.level,                 l.message,                 l.created_at,                 s.step_type,                 s.workflow_id,                 entry.original_name AS source_name             {self._GLOBAL_LOG_FROM}             {where}             ORDER BY l.created_at DESC, l.id DESC             LIMIT ? OFFSET ?             """,             [*params, limit, offset],)
        return [dict(r) for r in rows]

    async def close(self):
        if self._conn:
            await self._conn.close()


db = Database(os.path.join(settings.data_dir, "meta.db"))
storage = LocalStorage(Path(settings.data_dir) / "files")
