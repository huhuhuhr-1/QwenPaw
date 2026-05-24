import json

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..db import get_conn


def get_todo(task_id: str, **kwargs) -> ToolResponse:
    """Get a single task by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    if not row:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Task not found: {task_id}")],
        )

    task = dict(row)
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(task, ensure_ascii=False))],
    )
