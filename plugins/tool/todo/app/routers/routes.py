import time
import uuid
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter()


class UpdateTodoBody(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None


class CreateTodoBody(BaseModel):
    agent_name: str
    session_id: str
    session_title: Optional[str] = None
    description: str


@router.get("/")
def list_todos(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    time_from: Optional[float] = None,
    time_to: Optional[float] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    conn = get_conn()
    conditions = []
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if keyword:
        conditions.append("description LIKE ?")
        params.append(f"%{keyword}%")
    if time_from is not None:
        conditions.append("created_at >= ?")
        params.append(time_from)
    if time_to is not None:
        conditions.append("created_at <= ?")
        params.append(time_to)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM todos WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


@router.get("/{task_id}")
def get_todo(task_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(row)


@router.patch("/{task_id}")
def update_todo(task_id: str, body: UpdateTodoBody = Body(...)):
    conn = get_conn()
    row = conn.execute("SELECT id FROM todos WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    updates = []
    params = []
    if body.status is not None:
        updates.append("status = ?")
        params.append(body.status)
    if body.description is not None:
        updates.append("description = ?")
        params.append(body.description)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(task_id)

    conn.execute(f"UPDATE todos SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/")
def create_todo_internal(body: CreateTodoBody = Body(...)):
    task_id = str(uuid.uuid4())
    now = time.time()
    conn = get_conn()
    conn.execute(
        "INSERT INTO todos (id, agent_name, session_id, session_title, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, body.agent_name, body.session_id, body.session_title, body.description, "pending", now, now),
    )
    conn.commit()
    conn.close()
    return {"task_id": task_id}
