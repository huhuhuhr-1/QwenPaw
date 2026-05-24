import time

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..db import get_conn

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


def update_todo(
    task_id: str,
    status: str = None,
    description: str = None,
    **kwargs,
) -> ToolResponse:
    """Update a task's status and/or description."""
    if status is not None and status not in VALID_STATUSES:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}",
                )
            ],
        )

    conn = get_conn()
    row = conn.execute("SELECT id FROM todos WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Task not found: {task_id}")],
        )

    updates = []
    params = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(task_id)

    conn.execute(f"UPDATE todos SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()

    msg = f"Task {task_id} updated."
    if status:
        msg += f" Status → {status}."
    if description:
        msg += f" Description updated."

    return ToolResponse(content=[TextBlock(type="text", text=msg)])
