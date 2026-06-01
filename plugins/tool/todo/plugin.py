import sys
from pathlib import Path

__all__ = ["plugin"]

_PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(_PLUGIN_DIR))

from qwenpaw.plugins.api import PluginApi

from app.routers.routes import router
from app.db import init_db
from tools.create_todo import create_todo
from tools.get_todo import get_todo
from tools.list_todos import list_todos
from tools.update_todo import update_todo


class TodoPlugin:
    def register(self, api: PluginApi) -> None:
        api.register_http_router(router=router, prefix="/todo", tags=["todo"])

        api.register_tool(
            tool_name="create_todo",
            tool_func=create_todo,
            description="Create a new task. Args: description (str).",
            icon="📋",
        )
        api.register_tool(
            tool_name="get_todo",
            tool_func=get_todo,
            description="Get a single task by ID. Args: task_id (str).",
            icon="🔍",
        )
        api.register_tool(
            tool_name="update_todo",
            tool_func=update_todo,
            description="Update a task. Args: task_id (str), status (str, optional), description (str, optional).",
            icon="✏️",
        )
        api.register_tool(
            tool_name="list_todos",
            tool_func=list_todos,
            description="List tasks with optional filters. Args: status, keyword, limit, offset.",
            icon="📋",
        )

        api.register_startup_hook(
            hook_name="todo_init_db",
            callback=self._init_db,
            priority=10,
        )

    def _init_db(self) -> None:
        init_db()


plugin = TodoPlugin()
