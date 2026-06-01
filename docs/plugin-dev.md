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
      → import(blobURL)                    执行 IIFE
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
| `entry.frontend` | IIFE 构建产物的路径，相对于插件根目录 |
| `entry.backend` | Python 入口文件路径，必须 export `plugin` 对象 |
| `dependencies` | 声明式依赖列表，UI 展示用。**实际安装**看 `requirements.txt` |
| `min_version` | 所需的 QwenPaw 最低版本 |

---

## 4. 后端开发

### 4.1 入口文件 (plugin.py)

插件后端必须 export 一个 `plugin` 对象，实现 `register(api)` 方法：

```python
# plugin.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
PLUGIN_DIR = Path(__file__).parent


class MyPlugin:
    def register(self, api):
        """注册钩子 — 在 QwenPaw 启动时执行"""
        api.register_startup_hook(
            hook_name="my_plugin_init",
            callback=self._on_startup,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name="my_plugin_cleanup",
            callback=self._on_shutdown,
            priority=50,
        )

    async def _on_startup(self):
        """初始化：装 skills、启动子进程等"""
        ...

    async def _on_shutdown(self):
        """清理"""
        ...

plugin = MyPlugin()
```

### 4.2 PluginApi 注册能力

`register(api)` 收到的 `api` 参数提供以下注册方法：

```python
# src/qwenpaw/plugins/api.py

api.register_startup_hook(hook_name, callback, priority)     # 启动钩子
api.register_shutdown_hook(hook_name, callback, priority)     # 关闭钩子
api.register_http_router(router, prefix, tags)                # FastAPI 路由
api.register_provider(provider_id, provider_class, ...)       # LLM Provider
api.register_tool(tool_name, tool_func, description, ...)     # Agent 工具
api.register_control_command(handler, priority_level)         # 控制命令
```

### 4.3 后端子进程

插件通常以子进程方式启动独立的 FastAPI 服务：

```python
# plugin.py
def _start_backend_async():
    app_main = PLUGIN_DIR / "app" / "main.py"
    env = os.environ.copy()
    env["MY_PLUGIN_PORT"] = str(7899)

    return asyncio.subprocess.create_subprocess_exec(
        sys.executable, "-m", "app.main",       # 使用同一 Python
        cwd=str(PLUGIN_DIR),
        env=env,
    )


def _is_backend_running():
    """健康检查"""
    import httpx
    resp = httpx.get("http://localhost:7899/health", timeout=2)
    return resp.status_code == 200
```

**关键**：使用 `sys.executable` 而非硬编码 `python3`，确保与 QwenPaw 使用同一解释器，已安装的依赖可直接使用。

### 4.4 依赖管理

插件系统的依赖管理在 `loader.py:345-450`：

```python
# loader.py:521-528 — 自动检测 requirements.txt
requirements_file = target_dir / "requirements.txt"
if requirements_file.exists():
    await asyncio.to_thread(
        self._install_requirements,
        requirements_file,
        plugin_id,
    )
```

安装策略（`_install_requirements`）：

1. **优先** `python -m pip install -r requirements.txt`
2. **回退** `uv pip install --python <sys.executable> -r requirements.txt`（当 pip 不存在时）

> **注意**：只识别 `requirements.txt`，`pyproject.toml` 中的 `[project]dependencies` 不会被自动安装。

### 4.5 前端 API 通信模式

前端 `dist/index.js` 通过直接 HTTP 请求与后端子进程通信：

```typescript
const API_BASE = "http://localhost:7899";

async function api(method: string, url: string, body?: unknown) {
  const res = await fetch(`${API_BASE}${url}`, { method, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(...);
  return res.json();
}
```

后端子进程监听 `127.0.0.1:7899`，和 QwenPaw 主进程 (`:18006`) 独立。

### 4.6 三种路由注册模式

根据插件需求不同，后端 API 有三种注册方式：

---

#### 模式 A：`register_http_router` —— 同进程注册（推荐）

将 FastAPI `APIRouter` 直接挂载到 QwenPaw 主进程，**同进程**，零网络开销。

```python
# plugin.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
def status():
    return {"ok": True}

class MyPlugin:
    def register(self, api):
        api.register_http_router(router, prefix="/my-plugin", tags=["my-plugin"])

plugin = MyPlugin()
```

| 特点 | 说明 |
|------|------|
| 进程 | QwenPaw 主进程内，同进程 |
| 端口 | 复用 QwenPaw `:18006` |
| 前端访问 | `host.getApiUrl("/my-plugin/status")` |
| 适用场景 | 轻量 CRUD、配置读写、状态查询 |
| 示例插件 | `qwenpaw-pet` |

---

#### 模式 B：子进程独立 FastAPI 服务 —— 隔离运行

插件启动独立 FastAPI 子进程，**不同进程**，通过独立端口通信。

```python
# plugin.py
import asyncio, os, sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
_PROCESS_PORT = 7899

def _is_backend_running() -> bool:
    import httpx
    try:
        resp = httpx.get(f"http://localhost:{_PROCESS_PORT}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False

async def _ensure_backend():
    if _is_backend_running():
        return
    proc = await asyncio.subprocess.create_subprocess_exec(
        sys.executable, "-m", "app.main",
        cwd=str(PLUGIN_DIR),
        env={**os.environ, "PORT": str(_PROCESS_PORT)},
    )
```

| 特点 | 说明 |
|------|------|
| 进程 | 独立子进程，与 QwenPaw 隔离 |
| 端口 | 独立端口，建议从 `7899` 开始顺延 |
| 前端访问 | 直连 `http://localhost:{PORT}` |
| 适用场景 | 重型任务：音视频转码、模型推理、大文件处理 |
| 示例插件 | `data-processor` |

> **端口分配**：为避免冲突，新插件按顺序使用端口：`data-processor=7899`，下一个 `=7900`，依此类推。

---

#### 模式 C：手动注入运行中 App —— 在 QwenPaw 启动后注册

在 startup hook 中查找 QwenPaw 的 FastAPI 实例，手动挂载路由。需要处理 SPA catch-all 路由冲突。

```python
# routers_setup.py
def _inject_routers(routers: list) -> None:
    # 获取 QwenPaw 的 FastAPI app 实例
    from agentscope_runtime.engine.app import AgentApp
    agent_app = AgentApp._instances.get(AgentApp)
    app = agent_app.app

    for router in routers:
        app.include_router(router, prefix="/api")

    # 将 SPA catch-all `/{full_path:path}` 移到路由表末尾
    for i, r in enumerate(app.routes):
        if getattr(r, "path", "") == "/{full_path:path}":
            route = app.routes.pop(i)
            app.routes.append(route)

    # 重建中间件栈
    app.middleware_stack = None
```

| 特点 | 说明 |
|------|------|
| 进程 | QwenPaw 主进程内，同进程 |
| 复杂度 | 高，需手动处理 catch-all 和中间件栈 |
| 风险 | 依赖内部 API（`_instances`、`_app`），QwenPaw 升级可能失效 |
| 适用场景 | 历史遗留插件，不推荐新插件使用 |
| 示例插件 | `cloudpaw` |

---

#### 模式选择决策树

```
插件需要提供 API？
├─ API 很简单（CRUD / 状态查询）
│   └─ ✅ 模式 A：register_http_router
├─ API 有重型依赖（模型推理 / 转码 / FFmpeg）
│   └─ ✅ 模式 B：子进程（独立端口）
└─ 需要在 QwenPaw 启动后动态注册路由
    └─ ⚠️ 模式 C：手动注入（仅兼容遗留插件）
```

#### 端口规范速查

| 插件 | 模式 | 端口 |
|------|------|------|
| QwenPaw 主进程 | — | `18006` |
| data-processor | 子进程 | `7899` |
| 下一个子进程插件 | 子进程 | `7900` |
| ... | ... | 顺延 |

### 5.1 加载机制

```typescript
// console/src/plugins/usePluginLoader.ts:39-58
async function executePluginScript(entryUrl: string): Promise<void> {
  const jsText = await response.text();             // 文本获取
  const blobUrl = URL.createObjectURL(
    new Blob([jsText], { type: "application/javascript" }),
  );
  await import(/* @vite-ignore */ blobUrl);          // 动态 import 执行
  URL.revokeObjectURL(blobUrl);
}
```

所以：**插件是一个自包含的 `.js` 文件**，通过 `import(blobURL)` 执行，所有代码必须打包在一起（IIFE）。

### 5.2 开发环境

```json
// frontend/package.json — 最小依赖
{
  "devDependencies": {
    "vite": "^6.0.0",
    "typescript": "^5.0.0"
  }
}
```

`@vitejs/plugin-react` 不需要，因为不能使用 JSX（会导致 React 被打包进来）。

### 5.3 Vite 构建配置

```typescript
// vite.config.plugin.ts
import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    lib: {
      entry: resolve(__dirname, "src/plugin-entry.ts"),
      name: "MyPlugin",
      formats: ["iife"],
      fileName: () => "index.js",
    },
    rollupOptions: {
      external: [],           // 不 external，但也不 import 外部库
      output: {
        inlineDynamicImports: true,
      },
    },
    minify: false,
    sourcemap: true,
  },
});
```

### 5.4 入口文件模板

```typescript
// plugin-entry.ts — 自包含，零外部 import
import type { SomeType } from "./api/types";    // type-only 编译期擦除

const host = window.QwenPaw.host;
const React = host.React;
const antd = host.antd;
const antdIcons = (window as any).antdIcons || {};

function MyPage() {
  const [data, setData] = React.useState([]);
  // ... 全部使用 React.useXxx / antd.Button / antdIcons.xxx
}

function PluginRoot() {
  const [tab, setTab] = React.useState("main");
  // ... 用 state 做 tab 切换，不用 react-router
}

window.QwenPaw.registerRoutes?.("my-plugin", [{
  path: "/plugin/my-plugin",
  component: PluginRoot,
  label: "My Plugin",
  icon: "🔧",
  priority: 10,
}]);
```

### 5.5 核心限制

| 限制 | 原因 | 解决方案 |
|------|------|---------|
| 不能 `import React from "react"` | 没有 `node_modules`，打包会包含两份 React 导致 `$typeof` 冲突 | 从 `window.QwenPaw.host.React` 获取 |
| 不能使用 JSX | `@vitejs/plugin-react` 会引入 React 运行时 | 用 `React.createElement` |
| 不能嵌套 `<Router>` | 控制台已是 React Router v7 环境 | 用 state 做 tab 切换，不用 `useNavigate` |
| 所有代码打一个文件 | `import(blobURL)` 只能加载一个 entry | IIFE 格式 + `inlineDynamicImports: true` |
| 不能动态加载额外资源 | 只有一个 `.js` 文件 | 所有 CSS 内联、所有图片转 base64 |
| 图标只能用 antdIcons 或 Unicode | 无字体文件加载 | `const { SettingOutlined } = antdIcons` |

### 5.6 可用宿主资源

```typescript
window.QwenPaw.host = {
  React,              // React 全量
  antd,               // Ant Design 全量
  antdIcons,          // @ant-design/icons 全量
  ReactRouterDOM,     // react-router-dom（仅用于 Link/useNavigate 慎用）
  apiBaseUrl,         // QwenPaw API base URL
  getApiUrl,          // API URL 构造函数
  getApiToken,        // 获取认证 token
};

// 同时也挂在 window 上供 rollup globals 引用：
window.React
window.antd
window.ReactRouterDOM
window.antdIcons
```

### 5.7 注册路由

```typescript
window.QwenPaw.registerRoutes?.("plugin-id", [{
  path: "/plugin/plugin-id",
  component: PageComponent,
  label: "侧边栏显示名",
  icon: "⚙️",
  priority: 10,       // 越小越靠前
}]);
```

### 5.8 UI 组件注意

Ant Design 的 `Form.useForm()` / `Form.useWatch()` / `Modal` / `Table` 等均从 `antd` 对象获取，和正常 React 开发完全一致，只需注意用 `React.createElement` 写：

```typescript
// ❌ JSX（不支持）
return <Button type="primary">点击</Button>;

// ✅ React.createElement
return React.createElement(Button, { type: "primary" }, "点击");
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
npx vite build --config vite.config.ts
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

**原因**：插件打包了自己的 React，与宿主的 React 冲突，`$typeof` Symbol 不匹配。

**解决**：确保插件不 `import React from "react"`，全部从 `window.QwenPaw.host.React` 获取。

### Q2: `You cannot render a <Router> inside another <Router>`

**原因**：控制台使用 React Router v7，插件里又创建了 `<MemoryRouter>` 或 `<BrowserRouter>`。

**解决**：用 state 做 tab 切换，不要用任何 Router 组件：

```typescript
const [tab, setTab] = React.useState("files");
// 用条件渲染替代路由
const content = tab === "files" ? <FileList /> : <Settings />;
```

### Q3: `ReferenceError: process is not defined`

**原因**：Vite 构建时 `process.env.NODE_ENV` 未被替换，浏览器中 `process` 不存在。

**解决**：在 vite 配置中添加 `define: { "process.env.NODE_ENV": JSON.stringify("production") }`。

### Q4: `import.meta.env` is not available

**原因**：插件通过 IIFE + blob URL 加载，`import.meta` 不可用。

**解决**：硬编码 API 地址或在 vite config 中用 `define` 替换。

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
| `console/src/plugins/usePluginLoader.ts` | 前端加载和执行插件 IIFE |
| `plugins/data-processor/plugin.py` | 子进程模式后端示例 |
| `plugins/data-processor/app/main.py` | 子进程独立 FastAPI 应用 |
| `plugins/data-processor/frontend/src/plugin-entry.ts` | 完整插件前端示例 |
| `plugins/qwenpaw-pet/plugin.py` | `register_http_router` 模式示例 |
| `plugins/qwenpaw-pet/router.py` | FastAPI APIRouter 定义示例 |
| `plugins/cloudpaw/routers_setup.py` | 手动注入路由模式示例 |
| `plugins/tool/wan27/plugin.json` | tool 类型插件示例 |
