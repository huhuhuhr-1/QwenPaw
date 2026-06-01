#!/usr/bin/env python3
"""
todo 插件独立调试脚本
直接启动 FastAPI 服务，不依赖 QwenPaw 主程序

用法:
    python3 debug_server.py
    # 访问 http://localhost:8765/docs 查看 API 文档
"""

import sys
from pathlib import Path

# 注入插件目录到 Python 路径
_PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(_PLUGIN_DIR))

from app.db import init_db
from app.routers.routes import router
from tools.create_todo import create_todo
from tools.get_todo import get_todo
from tools.list_todos import list_todos
from tools.update_todo import update_todo

from fastapi import FastAPI
import uvicorn

# 初始化数据库
init_db()

# 创建独立 FastAPI 应用
app = FastAPI(
    title="todo Plugin Debug Server",
    version="0.1.0",
    description="独立调试模式，不依赖 QwenPaw 主程序",
)

# 注册路由
app.include_router(router, prefix="/todo", tags=["todo"])

# 注册工具函数为 API 端点（方便测试 Agent 工具）
@app.post("/debug/tools/create_todo")
def debug_create_todo(description: str):
    return create_todo(description=description)

@app.get("/debug/tools/get_todo")
def debug_get_todo(task_id: str):
    return get_todo(task_id=task_id)

@app.get("/debug/tools/list_todos")
def debug_list_todos(status: str = None, keyword: str = None, limit: int = 50, offset: int = 0):
    return list_todos(status=status, keyword=keyword, limit=limit, offset=offset)

@app.post("/debug/tools/update_todo")
def debug_update_todo(task_id: str, status: str = None, description: str = None):
    return update_todo(task_id=task_id, status=status, description=description)

# 数据库调试端点
@app.get("/debug/db")
def debug_db():
    conn = __import__('app.db', fromlist=['get_conn']).get_conn()
    rows = conn.execute("SELECT * FROM todos ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
    return {"todos": [dict(r) for r in rows]}

@app.delete("/debug/db")
def debug_db_clear():
    conn = __import__('app.db', fromlist=['get_conn']).get_conn()
    conn.execute("DELETE FROM todos")
    conn.commit()
    conn.close()
    return {"ok": True, "message": "All todos deleted"}

if __name__ == "__main__":
    print("=" * 50)
    print("todo 插件独立调试服务器")
    print("API 文档: http://localhost:8765/docs")
    print("按 Ctrl+C 停止")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8765, reload=False)