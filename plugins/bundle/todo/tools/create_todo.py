import time
import uuid

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..db import get_conn


def create_todo(description: str, **kwargs) -> ToolResponse:
    """Create a new task."""
    try:
        from ...app.agent_context import get_current_session_id, get_current_agent_id

        session_id = str(get_current_session_id() or "")
        agent_id = str(get_current_agent_id() or "unknown")
    except Exception:
        session_id = "unknown"
        agent_id = "unknown"

    task_id = str(uuid.uuid4())
    now = time.time()

    conn = get_conn()
    conn.execute(
        "INSERT INTO todos (id, agent_name, session_id, session_title, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, agent_id, session_id, None, description, "pending", now, now),
    )
    conn.commit()
    conn.close()

    return ToolResponse(
        content=[TextBlock(type="text", text=f"Task created: {task_id}\nDescription: {description}")],
    )
