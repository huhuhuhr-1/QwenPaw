import json

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..db import get_conn

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


def list_todos(
    status: str = None,
    keyword: str = None,
    limit: int = 50,
    offset: int = 0,
    **kwargs,
) -> ToolResponse:
    """List tasks with optional filtering."""
    if status and status not in VALID_STATUSES:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}",
                )
            ],
        )

    conn = get_conn()
    conditions = []
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if keyword:
        conditions.append("description LIKE ?")
        params.append(f"%{keyword}%")

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM todos WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    conn.close()

    tasks = [dict(r) for r in rows]
    if not tasks:
        return ToolResponse(content=[TextBlock(type="text", text="No tasks found.")])

    summary = f"Found {len(tasks)} task(s):\n"
    for t in tasks:
        summary += f"[{t['status']}] {t['id']} — {t['description'][:60]}\n"

    return ToolResponse(content=[TextBlock(type="text", text=summary)])
