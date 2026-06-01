# todo 插件

> Agent 任务管理 — 在会话中创建、跟踪和更新任务

---

## 一、功能概述

todo 插件为 QwenPaw Agent 提供任务管理能力：

| 功能 | 说明 |
|------|------|
| 创建任务 | Agent 通过 `create_todo` 工具创建新任务 |
| 查询任务 | 通过 `get_todo` 获取单个任务详情 |
| 更新任务 | 通过 `update_todo` 更新任务状态或描述 |
| 列出任务 | 通过 `list_todos` 列出所有任务，支持过滤 |

**数据存储**：SQLite 数据库 `~/.qwenpaw/data/todo.db`

**插件类型**：`frontend`（含 React 前端界面）

**集成模式**：轻量集成（HTTP 路由注册到 QwenPaw 主应用，非子服务）

---

## 二、架构设计

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      QwenPaw 主应用                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   React UI  │    │ Agent 引擎   │    │  PluginApi  │    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
│         │                  │                  │             │
│         │    /todo/* HTTP 路由                 │             │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    todo 插件 backend                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                 plugin.py (入口)                       │  │
│  │  - register_http_router() 注册 /todo 路由            │  │
│  │  - register_tool() 注册 Agent 工具                    │  │
│  │  - register_startup_hook() 初始化数据库               │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                    │
│    ┌────┴────┐                    ┌────────┐                 │
│    │ FastAPI │                    │ Agent  │                 │
│    │  路由    │                    │ 工具   │                 │
│    └────┬────┘                    └────────┘                 │
│         │                                                    │
│    ┌────┴────────────────────────────────────┐              │
│    │              app/routers/routes.py        │              │
│    │  GET  /todo/         列出任务             │              │
│    │  GET  /todo/{id}     获取任务             │              │
│    │  PATCH /todo/{id}    更新任务             │              │
│    └────┬────────────────────────────────────┘              │
│         │                                                    │
│    ┌────┴────────────────────────────────────┐              │
│    │              app/db.py                   │              │
│    │  SQLite: ~/.qwenpaw/data/todo.db        │              │
│    └─────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
plugins/todo/
├── plugin.json          # 清单（type: frontend）
├── plugin.py            # 插件入口，向 PluginApi 注册
├── requirements.txt    # Python 依赖
│
├── app/                 # 后端应用
│   ├── db.py           # SQLite 数据层
│   └── routers/        # FastAPI 路由
│       └── routes.py   # REST API 实现
│
├── tools/              # Agent 工具（供 Agent 调用）
│   ├── create_todo.py
│   ├── get_todo.py
│   ├── update_todo.py
│   └── list_todos.py
│
├── dist/               # 前端构建产物（打包时包含）
│   └── index.js
│
└── frontend/          # 前端源码（打包时排除）
    ├── src/
    ├── vite.config.ts
    └── package.json
```

### 2.3 数据模型

```sql
CREATE TABLE todos (
    id           TEXT PRIMARY KEY,      -- UUID
    agent_name   TEXT NOT NULL,         -- 创建任务的 Agent
    session_id   TEXT NOT NULL,         -- 关联的会话 ID
    session_title TEXT,                 -- 会话标题
    description  TEXT NOT NULL,        -- 任务描述
    status       TEXT NOT NULL,        -- pending|in_progress|completed|cancelled
    created_at   REAL NOT NULL,         -- 创建时间戳
    updated_at   REAL NOT NULL          -- 更新时间戳
);

CREATE INDEX idx_todos_session_id ON todos(session_id);
CREATE INDEX idx_todos_status ON todos(status);
```

---

## 三、关键实现

### 3.1 插件加载流程

```
QwenPaw 启动
  → PluginLoader.discover_plugins()    扫描 plugin.json
  → PluginLoader.load_plugin()          加载 plugin.py
  → TodoPlugin.register(api)            调用 register() 注册
      → register_http_router()           注册 /todo HTTP 路由
      → register_tool()                   注册 4 个 Agent 工具
      → register_startup_hook()           注册启动钩子
  → TodoPlugin._init_db()               执行 init_db() 初始化数据库
```

### 3.2 Agent 工具 vs HTTP API

| 用途 | 接口 | 调用方 |
|------|------|--------|
| Agent 使用 | `tools/create_todo` 等 | Agent 在 ReAct 循环中调用 |
| 用户界面 | `/todo/*` HTTP | React 前端通过 fetch 调用 |

两套接口都操作同一个 SQLite 数据库。

### 3.3 导入路径处理

```python
# plugin.py 顶部注入路径，使模块可独立导入
import sys
from pathlib import Path
_PLUGIN_DIR = Path(__file__).parent
sys.path.insert(0, str(_PLUGIN_DIR))

# 之后可用绝对导入
from app.routers.routes import router
from app.db import init_db
```

---

## 四、验证方法

### 4.1 安装插件

```bash
# 从打包文件安装
qwenpaw plugin install /opt/github/custome-qwenPaw-plugin/dist/todo.zip

# 从源码目录安装（开发模式）
qwenpaw plugin install /opt/github/custome-qwenPaw-plugin/plugins/todo --force
```

### 4.2 验证安装成功

```bash
# 检查插件是否在列表中
qwenpaw plugin list | grep todo

# 检查数据库文件是否存在
ls ~/.qwenpaw/data/todo.db
```

### 4.3 独立调试服务器

不依赖 QwenPaw 主程序，直接启动 FastAPI 服务：

```bash
cd /opt/github/custome-qwenPaw-plugin/plugins/todo
source .venv/bin/activate
python3 debug_server.py
```

输出：

```
==================================================
todo 插件独立调试服务器
API 文档: http://localhost:8765/docs
按 Ctrl+C 停止
==================================================
```

访问 http://localhost:8765/docs 使用 Swagger UI 测试所有接口。

### 4.4 API 测试

**HTTP API（调试服务器）**：

```bash
# 列出任务
curl http://localhost:8765/todo/

# 查看数据库
curl http://localhost:8765/debug/db

# 清空数据库
curl -X DELETE http://localhost:8765/debug/db
```

**Agent 工具测试**：

```bash
# 测试 create_todo
curl -X POST "http://localhost:8765/debug/tools/create_todo?description=测试任务"

# 测试 list_todos
curl "http://localhost:8765/debug/tools/list_todos"

# 测试 update_todo
curl -X POST "http://localhost:8765/debug/tools/update_todo?task_id=<id>&status=completed"
```

### 4.5 查看数据

```bash
# 直接查看 SQLite 数据库
sqlite3 ~/.qwenpaw/data/todo.db "SELECT * FROM todos;"

# 按状态筛选
sqlite3 ~/.qwenpaw/data/todo.db "SELECT * FROM todos WHERE status='pending';"
```

---

## 五、开发指南

### 5.1 环境搭建

```bash
cd /opt/github/custome-qwenPaw-plugin/plugins/todo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5.2 前端开发

```bash
cd /opt/github/custome-qwenPaw-plugin/plugins/todo/frontend

# 安装依赖
npm install

# 开发模式（热重载）
npm run dev

# 构建生产版本
npm run build
# 产物输出到 ../dist/index.js
```

### 5.3 打包验证

```bash
cd /opt/github/custome-qwenPaw-plugin
./scripts/pack.sh todo
```

### 5.4 重新安装

```bash
qwenpaw plugin install /opt/github/custome-qwenPaw-plugin/plugins/todo --force
```

### 5.5 目录职责

| 目录/文件 | 职责 |
|-----------|------|
| `plugin.py` | 插件入口，向 PluginApi 注册路由和工具 |
| `app/db.py` | SQLite 数据库操作 |
| `app/routers/routes.py` | FastAPI REST API 路由 |
| `tools/*.py` | Agent 工具函数实现 |
| `dist/index.js` | 前端构建产物 |
| `frontend/src/` | React 前端源码 |
| `debug_server.py` | 独立调试服务器 |

---

## 六、相关文档

- [文档入口](../../README.md)
- [插件开发经验](../../CLAUDE.md)