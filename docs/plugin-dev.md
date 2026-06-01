# QwenPaw Bundle 插件开发手册

> **本文档定位**：Bundle 插件（前后端完整插件）开发指南
>
> **快速入门** → [README.md](README.md) | **架构设计** → [architecture.md](architecture.md) | **工具插件开发** → [tools-dev.md](tools-dev.md)

## 目录

1. [插件系统架构](#1-插件系统架构)
2. [插件目录结构](#2-插件目录结构)
3. [plugin.json 元数据](#3-pluginjson-元数据)
4. [后端开发](#4-后端开发)
5. [前端开发](#5-前端开发)
6. [技能 (Skill) 集成](#6-技能-skill-集成)
7. [构建与部署](#7-构建与部署)
8. [常见问题](#8-常见问题)

---

## 1. 插件系统架构

QwenPaw 插件系统由三层组成：

```
Console (React 前端)
   │  GET /api/frontend_plugin 发现插件
   │  import(blob URL) 执行插件 JS
   ▼
Plugin Loader (Python, src/qwenpaw/plugins/)
   │  loader.py: PluginLoader — 发现、安装依赖、加载
   │  api.py: PluginApi — 暴露给插件的注册 API
   │  registry.py: PluginRegistry — 运行时注册中心
   ▼
Backend (插件子进程)
   │  plugin.py → register() → startup hooks → 启动后端服务
```

**加载流程**：

```
QwenPaw 启动
  → PluginLoader.discover_plugins()      扫描 plugins/ 目录下的 plugin.json
  → PluginLoader.load_plugin()           逐个加载
      → 解析 plugin.json
      → 有 requirements.txt? pip install     (loader.py:522-528)
      → importlib 动态加载 plugin.py
      → 调用 plugin.register(api)             (loader.py:210-215)
          → api.register_startup_hook(...)
          → api.register_shutdown_hook(...)
      → 启动后执行 startup hooks
          → 安装 skills 到 skill_pool
          → 启动后端子进程

Console 加载
  → GET /api/frontend_plugin              获取启用了前端的插件列表
  → usePluginLoader.ts: loadAllPlugins()
      → fetch(plugin frontend_entry)       下载 dist/index.js
      → import(blobURL)                    执行 ES 模块（React 外置）
      → window.QwenPaw.registerRoutes()    注册路由到控制台侧边栏
```

---

## 2. 插件目录结构

```
plugins/<plugin-id>/
├── plugin.json                 # 元数据（必需）
├── plugin.py                   # 后端入口（可选）
├── pyproject.toml              # Python 包信息（可选）
├── requirements.txt            # Python 依赖（可选，自动安装）
├── .env                        # 运行时配置（可选）
│
├── frontend/
│   └── dist/
│       └── index.js            # 前端构建产物（必需，有前端时）
│
├── app/                        # 后端 Python 代码
│   ├── main.py                 # FastAPI 入口
│   ├── config.py
│   ├── models/schemas.py
│   ├── routers/                # API 路由
│   │   ├── workflow/routes.py
│   │   ├── artifacts/routes.py
│   │   ├── logs/routes.py
│   │   ├── queue/routes.py
│   │   ├── config/routes.py
│   │   ├── upload/routes.py
│   │   ├── files/routes.py
│   │   ├── media/routes.py
│   │   ├── transcribe/routes.py
│   │   └── polish/routes.py
│   └── services/              # 业务逻辑
│       ├── pipeline/
│       ├── transcribe/
│       ├── artifacts/
│       ├── media/
│       └── workflow/
│
├── skills/                    # Agent 技能定义
│   ├── transcribe/SKILL.md
│   ├── polish/SKILL.md
│   ├── media/SKILL.md
│   └── workflow/SKILL.md
│
├── models/                    # ML 模型文件（可选，大文件）
│   └── whisper-large-v3/
│
├── data/                      # 运行时数据
│   ├── meta.db                # SQLite 数据库
│   └── files/                 # 上传/处理结果文件
│
└── scripts/                   # 辅助脚本（可选）
    └── download_whisper_model.py
```

> **注意**：精简部署时，`frontend/` 只需保留 `dist/`，源码和 `node_modules` 可删除。`tests/`、`pycache/`、`docker/`、`logs/` 均为非必需。

---

## 3. plugin.json 元数据

```json
{
  "id": "plugin-id",
  "name": "Display Name",
  "version": "0.1.0",
  "type": "frontend",
  "description": "Plugin description",
  "description_i18n": {
    "zh-CN": "中文描述",
    "en-US": "English description"
  },
  "author": "Author Name",
  "entry": {
    "frontend": "frontend/dist/index.js",
    "backend": "plugin.py"
  },
  "dependencies": [
    "httpx>=0.27.0",
    "fastapi>=0.110"
  ],
  "min_version": "1.1.7",
  "meta": {
    "category": "data-processing",
    "features": ["audio-transcription", "text-polishing"]
  }
}
```

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识，用作目录名和注册名 |
| `type` | `"frontend"` = 出现在控制台侧边栏；`"general"` = 不显示 |
| `entry.frontend` | ES 模块构建产物的路径，相对于插件根目录 |
| `entry.backend` | Python 入口文件路径，必须 export `plugin` 对象 |
| `dependencies` | 声明式依赖列表，UI 展示用。**实际安装**看 `requirements.txt` |
| `min_version` | 所需的 QwenPaw 最低版本 |

---

## 4. 后端开发

> **本章节规范** 适用于所有 Bundle 插件（`type: frontend` / `type: general`）。Tool 插件请看 [tools-dev.md](tools-dev.md)。

### 4.0 目录布局（后端部分）

```
plugins/<plugin-id>/
├── plugin.py                # 入口：导出 plugin 对象（必需）
├── requirements.txt         # Python 依赖（UTF-8 无 BOM）
├── plugin.json              # 元数据（见第 3 章）
├── app/                     # 模式 B 子进程后端
│   ├── main.py              # FastAPI 应用 + lifespan
│   ├── config.py            # Pydantic BaseSettings（必需）
│   ├── database.py          # aiosqlite 封装
│   ├── routers/             # APIRouter 集合
│   │   └── routes.py
│   └── services/            # 业务逻辑（可选）
├── routers/                 # 模式 A 路由（与 app/ 平级）
│   └── routes.py
├── tools/                   # Agent 工具函数（可选）
└── skills/<name>/SKILL.md   # Agent 技能（可选）
```

### 4.1 入口文件 (plugin.py)

插件后端必须 export 一个 `plugin` 对象，实现 `register(api)` 方法。生命周期：

- `register(api)` 在 **模块 import 时**调用 — 只注册 hook，不做实际工作
- `_on_startup` 在 **QwenPaw 启动后**调用 — 装 skills、起子进程、init DB
- `_on_shutdown` 在 **QwenPaw 关闭时**调用 — 关子进程、flush DB

```python
# -*- coding: utf-8 -*-
"""<Plugin Name> —— <一句话描述>"""

__all__ = ["plugin"]

import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from qwenpaw.plugins.api import PluginApi

# 标准 logger 命名：用 __name__，让日志归到正确模块
logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent
_PLUGIN_ID = "my-plugin"                 # 必须 = plugin.json.id
_PLUGIN_SKILLS: tuple[str, ...] = ()     # 有 skills 才填
_PROCESS_PORT = 7899                     # 模式 B 才用


# ── Skill 安装（可选） ──────────────────────────────────


def _install_plugin_skills() -> None:
    """将插件 skills 复制到 ~/.qwenpaw/skill_pool/，并更新 manifest。"""
    try:
        from qwenpaw.agents.skill_system import (
            ensure_skill_pool_initialized,
            get_skill_pool_dir,
        )
    except ImportError:
        logger.warning("skill_system 不可用，跳过 skill 安装")
        return

    try:
        ensure_skill_pool_initialized()
    except Exception as exc:
        logger.warning("Skill pool init failed: %s", exc)

    pool_dir = get_skill_pool_dir()
    for name in _PLUGIN_SKILLS:
        src = PLUGIN_DIR / "skills" / name
        dst = pool_dir / name
        if not src.exists():
            logger.warning("插件 skill 源缺失: %s", src)
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    _update_pool_manifest(pool_dir)


def _update_pool_manifest(pool_dir: Path) -> None:
    """把插件 skills 写入 pool 的 skill.json。"""
    import json
    manifest_path = pool_dir / "skill.json"
    try:
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.exists()
            else {"skills": {}, "builtin_skill_names": []}
        )
    except Exception as exc:
        logger.warning("读取 pool manifest 失败: %s", exc)
        return

    skills = manifest.setdefault("skills", {})
    for name in _PLUGIN_SKILLS:
        if (pool_dir / name).exists() and name not in skills:
            skills[name] = {
                "source": f"plugin:{_PLUGIN_ID}",
                "protected": False,
            }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── 子进程管理（模式 B 才用） ────────────────────────────


def _is_backend_running() -> bool:
    """健康检查 — 复用 httpx 已有依赖即可。"""
    import httpx
    try:
        return httpx.get(
            f"http://127.0.0.1:{_PROCESS_PORT}/health", timeout=2,
        ).status_code == 200
    except Exception:
        return False


async def _ensure_backend() -> None:
    """启动 FastAPI 子进程（幂等）。"""
    if _is_backend_running():
        logger.info("[%s] backend already running", _PLUGIN_ID)
        return

    app_main = PLUGIN_DIR / "app" / "main.py"
    if not app_main.exists():
        logger.warning("[%s] app/main.py 不存在，后端未启动", _PLUGIN_ID)
        return

    logger.info("[%s] starting backend on port %d", _PLUGIN_ID, _PROCESS_PORT)
    env = os.environ.copy()
    # env 用 <PLUGIN>_PORT 前缀，避免多插件冲突
    env[f"{_PLUGIN_ID.upper().replace('-', '_')}_PORT"] = str(_PROCESS_PORT)

    proc = await asyncio.subprocess.create_subprocess_exec(
        sys.executable, "-m", "app.main",       # 使用同一 Python
        cwd=str(PLUGIN_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # 等 uvicorn 起来；正式判定用 _is_backend_running()
    await asyncio.sleep(2)


# ── Plugin 入口 ──────────────────────────────────────────


class MyPlugin:
    def register(self, api: PluginApi) -> None:
        """注册钩子、路由、工具 — 仅在 import 时执行。"""
        # 模式 A：同进程 HTTP 路由
        # from routers.routes import router
        # api.register_http_router(router, prefix=f"/{_PLUGIN_ID}", tags=[_PLUGIN_ID])

        # 可选：注册 Agent 工具
        # from tools.my_tool import my_tool
        # api.register_tool(tool_name="my_tool", tool_func=my_tool,
        #                   description="...", icon="🛠️")

        api.register_startup_hook(
            hook_name=f"{_PLUGIN_ID}_startup",
            callback=self._on_startup,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name=f"{_PLUGIN_ID}_shutdown",
            callback=self._on_shutdown,
            priority=50,
        )
        logger.info("[%s] plugin registered", _PLUGIN_ID)

    async def _on_startup(self) -> None:
        logger.info("[%s] starting up", _PLUGIN_ID)
        # 1. 装 skills（如果有）
        if _PLUGIN_SKILLS:
            _install_plugin_skills()
        # 2. 模式 B：起子进程
        # await _ensure_backend()

    async def _on_shutdown(self) -> None:
        logger.info("[%s] shutting down", _PLUGIN_ID)


plugin = MyPlugin()
```

### 4.2 PluginApi 注册能力

`register(api)` 收到的 `api` 参数提供以下注册方法：

```python
api.register_startup_hook(hook_name, callback, priority)     # 启动钩子
api.register_shutdown_hook(hook_name, callback, priority)     # 关闭钩子
api.register_http_router(router, prefix, tags)                # FastAPI 路由
api.register_provider(provider_id, provider_class, ...)       # LLM Provider
api.register_tool(tool_name, tool_func, description, ...)     # Agent 工具
api.register_control_command(handler, priority_level)         # 控制命令
```

### 4.3 配置管理（Pydantic BaseSettings — 必需）

**统一用 Pydantic BaseSettings**，不要再用 `os.getenv` 散写。配置可被环境变量和 `.env` 双重覆盖。

```python
# app/config.py
"""<插件名> 配置"""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """所有配置用 env_prefix 防止与全局环境变量冲突。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="MY_PLUGIN_",            # 防止与环境变量冲突
        extra="ignore",
        populate_by_name=True,
    )

    # ── Server ──
    host: str = "127.0.0.1"
    port: int = 7899

    # ── Storage ──
    data_dir: str = str(Path.home() / ".qwenpaw" / "data" / "my-plugin")
    db_path: str = ""                      # 由 model_validator 派生

    # ── 第三方 API（用 AliasChoices 兼容两种命名） ──
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEY", "MY_PLUGIN_API_KEY"),
    )

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        # pydantic v2：用 __setattr__ 避免 frozen；或用 computed_field
        if not self.db_path:
            object.__setattr__(
                self, "db_path", str(Path(self.data_dir) / "my-plugin.db"),
            )


settings = Settings()
```

**关键约束**：
- 统一用 `env_prefix="<PLUGIN_ID>_"`，避免与 QwenPaw 主进程环境变量冲突
- **DB 路径必须** = `~/.qwenpaw/data/<plugin-id>.db`（PyInstaller 打包后插件目录只读）

### 4.4 数据库（统一用 aiosqlite）

**所有 Bundle 插件的数据库都用 `aiosqlite`**，不要用同步 `sqlite3`。

理由：FastAPI 是异步的，路由函数默认跑在事件循环里；同步 sqlite 调用会阻塞事件循环，并发请求会卡死。同步 sqlite + `check_same_thread=False` 只是把崩溃推迟，并发场景下依然会损坏。

```python
# app/database.py
"""<插件名> 数据库"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接 — 调用方负责 close。"""
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(settings.db_path, timeout=30.0)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """启动时建表。"""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        """)
        await db.commit()
        logger.info("database initialized: %s", settings.db_path)
    finally:
        await db.close()


# ── CRUD 示例 ──

async def list_items(keyword: str = "", limit: int = 50) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM items WHERE name LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{keyword}%", limit),
        )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()
```

### 4.5 模式 A vs 模式 B 决策树

```
插件需要提供 API？
├─ API 很简单（CRUD / 状态查询 / 配置读写）
│   └─ ✅ 模式 A：register_http_router（同进程，零网络开销）
│
├─ API 有重型依赖（psutil、whisper、FFmpeg、模型推理）
│   └─ ✅ 模式 B：子进程（独立端口，从 7899 顺延）
│
└─ 需要在 QwenPaw 启动后动态注册路由
    └─ ⚠️ 模式 C：手动注入（仅兼容遗留插件，新插件禁止用）
```

#### 模式 A：`register_http_router`（推荐）

```python
# plugin.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status():
    return {"ok": True}


class MyPlugin:
    def register(self, api):
        # prefix 统一用 /<plugin-id>，主进程会自动加 /api
        api.register_http_router(router, prefix="/my-plugin", tags=["my-plugin"])
```

| 特点 | 说明 |
|------|------|
| 进程 | QwenPaw 主进程内，同进程 |
| 端口 | 复用 QwenPaw `:18006`，前端走 `host.getApiUrl("/my-plugin/...")` |
| 适用场景 | 轻量 CRUD、状态查询、配置读写 |
| 参考插件 | `qwenpaw-pet` / `todo` |

#### 模式 B：子进程独立 FastAPI（重型任务）

端口从 `7899` 开始顺延（`7899 → 7900 → 7901 → ...`），**禁止占用主进程 `:18006`**。

模式 B 插件的子进程**端口必须**用 `env_prefix` 化的环境变量（见 4.1 节），避免多插件相互覆盖 `PORT`。

env var 命名约定：`<PLUGIN_ID_UPPER>_PORT`，例如 `MY_PLUGIN_PORT=7899`。

#### 模式 C：手动注入运行中 App

⚠️ **新插件禁止用**。仅兼容 `cloudpaw` 这类历史遗留，依赖 QwenPaw 内部 API（`_instances` / `_app`），升级时易失效。

如需了解，见 4.7 节的"模式 C 参考"。

### 4.6 依赖管理

**`requirements.txt` 与 `plugin.json.dependencies` 必须严格对齐**，只在一处维护，每次发布前 diff。

| 文件 | 用途 |
|------|------|
| `requirements.txt` | 实际安装 — loader 自动 `pip install -r` |
| `plugin.json.dependencies` | UI 展示，**不要漏** |

**BOM 必检**：`requirements.txt` 必须是 UTF-8 **无 BOM**。BOM（`EF BB BF` 三个隐藏字节）会导致 `str.strip()` 删不掉，第一行依赖被静默跳过。

```bash
# 检测 BOM
head -c 3 requirements.txt | xxd | grep "efbb bf" && echo "有BOM" || echo "无BOM"
# 移除 BOM
sed -i '1s/^\xEF\xBB\xBF//' requirements.txt
```

### 4.7 模式 C 参考（仅遗留插件）

> ⚠️ 本节描述的是**遗留模式**，新插件**不要使用**。阅读本节仅用于维护 `cloudpaw` 等历史插件。

```python
# routers_setup.py
def _inject_routers(routers: list) -> None:
    from agentscope_runtime.engine.app import AgentApp
    agent_app = AgentApp._instances.get(AgentApp)
    app = agent_app.app

    for router in routers:
        app.include_router(router, prefix="/api")

    # 关键：把 SPA catch-all `/{full_path:path}` 移到路由表末尾
    for i, r in enumerate(app.routes):
        if getattr(r, "path", "") == "/{full_path:path}":
            route = app.routes.pop(i)
            app.routes.append(route)

    # 重建中间件栈，让新路由生效
    app.middleware_stack = None
```

### 5. 前端开发

> **本章节规范** 适用于所有有 UI 的 Bundle 插件（`type: frontend`）。`type: general` 插件无前端可跳过。

#### 5.0 目录布局

```
plugins/<plugin-id>/
└── frontend/                # 前端源码目录（统一命名，禁 ui/）
    ├── package.json         # npm 依赖
    ├── tsconfig.json        # TS 配置
    ├── vite.config.ts       # Vite 配置
    └── src/
        ├── index.tsx        # 入口（注册路由 + 暴露插件类）
        ├── pages/           # 页面组件
        │   └── MyPage.tsx
        ├── api.ts           # API 封装（用 host.getApiUrl + authHeaders）
        ├── types.ts         # 业务类型
        └── qwenpaw-host.d.ts  # 宿主 window.QwenPaw 类型声明（必需）

frontend/dist/index.js       # ★ 构建产物（plugin.json entry.frontend 指向它）
```

#### 5.1 加载机制

```typescript
// console/src/plugins/usePluginLoader.ts
async function executePluginScript(entryUrl: string): Promise<void> {
  const jsText = await response.text();
  const blobUrl = URL.createObjectURL(
    new Blob([jsText], { type: "application/javascript" }),
  );
  await import(/* @vite-ignore */ blobUrl);   // 动态 import 执行
  URL.revokeObjectURL(blobUrl);
}
```

所以：**插件是一个 ES 模块 `.js` 文件**，通过 `import(blobURL)` 执行，**React 不打包进去**——必须外置（`external: ["react", "react-dom"]`），由宿主 `window.React` 注入。

#### 5.2 package.json 最小依赖

```json
{
  "name": "<plugin-id>-frontend",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "build": "vite build",
    "dev": "vite build --watch",
    "format": "tsc --noEmit && prettier --write --cache .",
    "format:check": "tsc --noEmit && prettier --check ."
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@vitejs/plugin-react": "^4.3.1",
    "prettier": "3.0.0",
    "typescript": "^5.5.4",
    "vite": "^5.4.2"
  }
}
```

> **必装** `@vitejs/plugin-react` 和 `@types/react`——新规范下 JSX 是一等公民。

#### 5.3 Vite 构建配置（统一标准）

```typescript
// frontend/vite.config.ts
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react({ jsxRuntime: "classic" })],   // ← 关键
  resolve: { alias: { "@": resolve(__dirname, "src") } },
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.tsx"),
      formats: ["es"],                            // ← ES 模块，不打包 React
      fileName: () => "index.js",
    },
    outDir: resolve(__dirname, "dist"),           // ← 产物到 frontend/dist/
    emptyOutDir: true,
    rollupOptions: {
      external: ["react", "react-dom"],           // ← 外置宿主 React
    },
    minify: false,                                // 调试友好
    sourcemap: true,
  },
});
```

#### 5.4 tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react",                               // ← 必须 react，不是 preserve
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": []                                   // ← 关键：避免 React 全局冲突
  },
  "include": ["src"]
}
```

> **`types: []` 必要性**：`@types/react` 会 `export as namespace React` 把 `React` 注册为全局，与 `const React = host.React` 冲突（`Cannot redeclare block-scoped variable 'React'`）。`types: []` 关掉自动注册，宿主类型由 `qwenpaw-host.d.ts` 显式声明。

#### 5.5 宿主类型声明（必需）

```typescript
// frontend/src/qwenpaw-host.d.ts
import type * as ReactNS from "react";

declare global {
  interface QwenPawHost {
    React: typeof ReactNS;
    antd: any;                                 // antd 公开类型太大，结构 any 即可
    antdIcons?: any;
    getApiUrl: (path: string) => string;
    getApiToken: () => string;
  }
  interface QwenPawRoute {
    path: string;
    component: unknown;
    label?: string;
    icon?: string;
    priority?: number;
  }
  interface QwenPawGlobal {
    host: QwenPawHost;
    registerRoutes?: (id: string, routes: QwenPawRoute[]) => void;
    registerToolRender?: (
      id: string,
      renderers: Record<string, React.FC<any>>,
    ) => void;
  }
  interface Window { QwenPaw: QwenPawGlobal; }
}
export {};
```

> 不声明这份 d.ts，`host.antd` / `host.getApiUrl` 等会退化成 `any`，宿主 API 漂移时编译器不会报错。

#### 5.6 入口文件模板

```tsx
// frontend/src/index.tsx
import type * as ReactNS from "react";
import { MyPage } from "./pages/MyPage";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;

class MyPlugin {
  readonly id = "my-plugin";                  // 必须 = plugin.json.id

  setup(): void {
    window.QwenPaw.registerRoutes?.(this.id, [{
      path: "/plugin/my-plugin",
      component: MyPage,
      label: "My Plugin",
      icon: "🛠️",
      priority: 50,                          // 越小越靠前
    }]);
  }
}

new MyPlugin().setup();
```

```tsx
// frontend/src/pages/MyPage.tsx
import type * as ReactNS from "react";
import { api } from "../api";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;
const { Card, Table, Button, message } = host.antd;

export function MyPage() {
  const [items, setItems] = React.useState<Item[]>([]);
  const [loading, setLoading] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ items: Item[] }>("/my-plugin/items");
      setItems(data.items);
    } catch (e: any) {
      message.error(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { void refresh(); }, [refresh]);

  return (
    <Card title="My Items">
      <Table rowKey="id" loading={loading} dataSource={items}
             columns={[
               { title: "Name", dataIndex: "name" },
               { title: "Action", render: (_, r) =>
                 <Button onClick={() => api.delete(`/my-plugin/items/${r.id}`).then(refresh)}>
                   Delete
                 </Button> },
             ]} />
    </Card>
  );
}
```

#### 5.7 API 封装（统一标准）

```typescript
// frontend/src/api.ts
function getSelectedAgentId(): string | null {
  try {
    const raw =
      window.sessionStorage?.getItem("qwenpaw-agent-storage") ??
      window.localStorage?.getItem("qwenpaw-agent-storage");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const selected = parsed?.state?.selectedAgent;
    return typeof selected === "string" && selected ? selected : null;
  } catch {
    return null;
  }
}

export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const t = window.QwenPaw.host.getApiToken?.();
  if (t) headers.Authorization = `Bearer ${t}`;
  const agentId = getSelectedAgentId();
  if (agentId) headers["X-Agent-Id"] = agentId;
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(window.QwenPaw.host.getApiUrl(path), {
    ...init,
    headers: { ...init?.headers, ...authHeaders() },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  get:    <T>(p: string) => request<T>(p),
  post:   <T>(p: string, body: unknown) =>
    request<T>(p, { method: "POST",  headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  patch:  <T>(p: string, body: unknown) =>
    request<T>(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};
```

**约束**：
- 永远用 `host.getApiUrl` + `host.getApiToken`，**禁止硬编码 URL**（如 `http://localhost:7900`）
- 模式 A：直接走 `getApiUrl("/my-plugin/...")`，宿主主进程 `:18006` 处理
- 模式 B：把子进程路由桥接到主进程（`register_http_router(router, prefix="/my-plugin")`），前端仍走 `getApiUrl`
- 模式 B 子进程裸跑（不桥接）时仍要 `authHeaders` + 透传，否则 dev 之外环境鉴权失败

#### 5.8 核心限制

| 限制 | 原因 | 解决方案 |
|------|------|---------|
| 不能 `import React from "react"` | 宿主已经有一份 React，再 import 会双 `$typeof` 冲突（Minified React error #31） | `const React: typeof ReactNS = host.React` |
| 不能 `import { Button } from "antd"` | 同上 | `const { Button } = host.antd` |
| 不能 `import { SettingOutlined } from "@ant-design/icons"` | 同上 | `const { SettingOutlined } = host.antdIcons` |
| 不能嵌套 `<Router>` | 宿主已是 React Router v7 | `useState` 做 tab 切换，不用 `useNavigate` |
| 不能用 `process.env` / `import.meta.env` | 插件通过 `import(blobURL)` 执行，`import.meta` 不存在 | 硬编码或 vite `define` 替换 |
| 不能动态加载额外 JS/CSS/字体 | 只有一个 ES 文件 | 所有 CSS 内联、图片转 base64 |
| 不能 `new` 路由/重写 | 路由由宿主 React Router 控制 | 只能用 `registerRoutes` 追加 |

#### 5.9 注册路由

```typescript
window.QwenPaw.registerRoutes?.(pluginId, [{
  path: "/plugin/plugin-id",     // 必须以 /plugin/ 开头
  component: PageComponent,
  label: "侧边栏显示名",
  icon: "⚙️",                    // emoji 或 antdIcons 名称
  priority: 10,                  // 越小越靠前
}]);
```

`registerRoutes` 是**可选链**（`?.`）—— 宿主未挂载 `window.QwenPaw` 时不应崩溃。

#### 5.10 可用宿主资源

```typescript
window.QwenPaw.host = {
  React,              // React 全量
  antd,               // Ant Design 全量
  antdIcons,          // @ant-design/icons 全量
  ReactRouterDOM,     // react-router-dom（慎用：宿主已用 React Router v7）
  apiBaseUrl,         // QwenPaw API base URL
  getApiUrl,          // API URL 构造函数
  getApiToken,        // 获取认证 token
};
```

---

## 6. 技能 (Skill) 集成

插件可以在启动时将自己的 skill 安装到 QwenPaw 的全局 skill pool 中，使 Agent 能够使用。

### 6.1 Skill 目录结构

```
skills/<skill-name>/
└── SKILL.md
```

SKILL.md 示例：

```yaml
---
name: transcribe
description: Audio/Video transcription skill
metadata:
  source: plugin:data-processor
---
# Transcribe Skill

You can use this skill to transcribe audio and video files...
```

### 6.2 安装机制

通过 `_install_plugin_skills()` 将插件 skills 复制到全局 pool：

```python
# plugin.py
_PLUGIN_SKILLS = ("transcribe", "polish", "media", "workflow")

def _install_plugin_skills():
    from qwenpaw.agents.skill_system import get_skill_pool_dir

    pool_dir = get_skill_pool_dir()           # ~/.qwenpaw/skill_pool/
    skills_src = PLUGIN_DIR / "skills"

    for skill_name in _PLUGIN_SKILLS:
        src = skills_src / skill_name
        dst = pool_dir / skill_name
        if dst.exists():
            shutil.rmtree(dst)                # 覆盖旧版本
        shutil.copytree(src, dst)             # 复制到 pool
```

### 6.3 Agent 加载链路

```
plugin.py:_on_startup
  → _install_plugin_skills()
    → 复制到 ~/.qwenpaw/skill_pool/<skill-name>/SKILL.md
    → 更新 skill.json manifest

Agent 初始化 (ReActLoop)
  → skill_system.registry
    → scan(skill_pool/)
    → 发现 SKILL.md → 注册 skill
    → Agent 可用 skill 列表包含该 skill
```

### 6.4 注册时机

Skills 的安装发生在 **QwenPaw 启动时**的 startup hook 中（`_on_startup`），早于 Agent 初始化，因此 Agent 启动时就能看到这些 skill。

---

## 7. 构建与部署

### 7.1 构建前端

前端由打包脚本自动构建：

```bash
# 打包单个插件（自动构建前端）
./scripts/pack.sh <插件ID>

# 打包所有插件
./scripts/pack.sh
```

打包脚本会自动检测 `frontend/package.json` → `npm install` → `vite build` → 输出 `frontend/dist/index.js`。

也可以手动构建：

```bash
cd plugins/<plugin-id>/frontend
npm install
npm run build
# 输出: frontend/dist/index.js
```

### 7.2 部署到 QwenPaw

```bash
# 部署到插件目录（内置 bundle 时自动发现）
cp frontend/dist/index.js ~/.qwenpaw/plugins/<plugin-id>/frontend/dist/

# 重启
qwenpaw app --port 18006
```

### 7.3 精简清单

运行时不必要、可删除的文件：

| 路径 | 原因 | 典型大小 |
|------|------|---------|
| `frontend/node_modules/` | npm 开发依赖 | 300MB+ |
| `frontend/src/` | 前端源码（保留 dist/ 即可） | 不定 |
| `frontend/package.json` | npm 配置 | — |
| `frontend/vite.config.*` | 构建配置 | — |
| `frontend/*.config.*` | TypeScript/ESLint 配置 | — |
| `frontend/index.html` | 开发用 HTML | — |
| `frontend/logs/` | 构建日志 | 不定 |
| `logs/` | 后端日志 | 不定 |
| `tests/`, `**/__pycache__/` | 测试和字节码缓存 | 不定 |
| `docker/` | Docker 配置 | 不定 |
| `uv.lock` | 依赖锁文件 | — |
| `.venv/` | 本地开发虚拟环境 | 800MB+ |

---

## 8. 常见问题

### Q1: `Minified React error #31` / `Cannot read properties of null (reading 'useRef')`

**原因**：插件打包了自己的 React（或 antd），与宿主的 React 冲突，`$typeof` Symbol 不匹配。

**解决**：
1. 检查 `vite.config.ts` 是否设置 `external: ["react", "react-dom"]`
2. 源码全部从 `host.React` / `host.antd` 取，**禁止** `import React from "react"`、`import { Button } from "antd"`
3. 入口用 `import type * as ReactNS from "react"`（仅类型）

### Q2: `You cannot render a <Router> inside another <Router>`

**原因**：控制台使用 React Router v7，插件里又创建了 `<MemoryRouter>` 或 `<BrowserRouter>`。

**解决**：用 state 做 tab 切换，不要用任何 Router 组件：

```tsx
const [tab, setTab] = React.useState("files");
const content = tab === "files" ? <FileList /> : <Settings />;
```

### Q3: `ReferenceError: process is not defined`

**原因**：打包时 `process.env.NODE_ENV` 未被替换，浏览器中 `process` 不存在。常见于引入了带 Node 全局的 npm 库（如 polyfill 库）。

**解决**：在 vite 配置中添加 `define: { "process.env.NODE_ENV": JSON.stringify("production") }`，或换不带 Node 假设的库。

### Q4: `import.meta.env` is not available

**原因**：插件通过 `import(blobURL)` 加载，`import.meta` 在 blob 模块上下文中不可用。

**解决**：硬编码 API 地址；或在 vite config 中用 `define: { __MY_VAR__: JSON.stringify("...") }` 替换。

### Q5: 插件不出现在侧边栏

**原因**：`plugin.json` 中 `type` 为 `"general"` 或未设置。

**解决**：设置为 `"type": "frontend"`。

### Q6: 后端依赖报 `ModuleNotFoundError`

**原因**：`requirements.txt` 缺失或未被自动安装。

**解决**：在插件根目录创建 `requirements.txt`，插件加载器会自动 `pip install -r requirements.txt`。

### Q7: Skill 没有生效

**原因**：Skill 未正确复制到 pool，或 pool manifest 未更新。

**解决**：检查 `plugin.py` 中 `_install_plugin_skills()` 是否正确调用，确认 `~/.qwenpaw/skill_pool/<name>/SKILL.md` 存在。

### Q8: `requirements.txt` 第一行依赖永远不生效

**原因**：文件开头包含 UTF-8 BOM（`﻿`），`str.strip()` 无法删除 BOM（不是空白字符），导致 `Requirement('﻿fastapi==...')` 解析失败后被 `except Exception: continue` 静默跳过。

**症状**：插件反复尝试安装依赖，或提示 "Plugin loader is not ready yet"。

**解决**：用支持 UTF-8 无 BOM 的编辑器（如 VS Code）重新保存 `requirements.txt`，或手动删除文件首部的 `﻿` 字符。

---

## 附录：代码文件参考

| 文件 | 用途 |
|------|------|
| `src/qwenpaw/plugins/loader.py` | 插件加载器：发现、安装依赖、动态 import |
| `src/qwenpaw/plugins/api.py` | PluginApi：插件可用的全部注册 API |
| `src/qwenpaw/plugins/registry.py` | PluginRegistry：运行时注册中心 |
| `console/src/plugins/hostExternals.ts` | 宿主依赖暴露给插件 |
| `console/src/plugins/usePluginLoader.ts` | 前端加载和执行插件 ES 模块 |
| `plugins/bundle/qwenpaw-pet/plugin.py` | `register_http_router` 模式示例（推荐） |
| `plugins/bundle/qwenpaw-pet/router.py` | FastAPI APIRouter 定义示例 |
| `plugins/bundle/qwenpaw-pet/frontend/src/index.tsx` | 完整插件前端示例（ES + JSX + 外置 React） |
| `plugins/bundle/qwenpaw-pet/frontend/src/qwenpaw-host.d.ts` | 宿主 window.QwenPaw 类型声明示例 |
| `plugins/bundle/media-studio/plugin.py` | 模式 B 子进程后端示例 |
| `plugins/bundle/media-studio/app/main.py` | 子进程独立 FastAPI 应用 |
| `plugins/bundle/todo/plugin.py` | 模式 A + aiosqlite 同步 CRUD 示例 |
| `plugins/bundle/cloudpaw/routers_setup.py` | 模式 C 手动注入路由示例（仅遗留） |
| `plugins/tool/wan27/plugin.json` | tool 类型插件示例 |
