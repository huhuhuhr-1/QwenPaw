# HANDOFF.md — 插件异步安装

## 目标

解决 Ubuntu 上安装插件一直卡在"安装中"的问题。当前插件安装是同步阻塞的 HTTP 请求（下载→解压→pip install→import→hooks→agent reload 全部在一个 POST 里完成），前端 `fetch()` 无超时，任一环节卡住就永远显示"安装中"。

**方案**：改为异步安装 — API 立即返回 task_id，后台处理，前端轮询状态。

## 当前进度

**已完成：**
- 完整分析了插件安装的前后端全流程
- 确定了设计方案的最终计划文件：`/home/hr/.claude/plans/declarative-splashing-gosling.md`

**尚未开始实施。**

## 分析总结

### 根因

- `console/src/api/modules/plugin.ts` 中的 `fetch()` 无超时
- `src/qwenpaw/app/routers/plugins.py` 中 install/upload 端点同步执行全部操作
- `_post_load_setup()` 中的 startup hooks 和 `_install_requirements()` 的 pip/uv（最长300s timeout）可能阻塞

### 关键文件（已读取）

| 文件 | 作用 |
|---|---|
| `src/qwenpaw/app/routers/plugins.py` | 后端路由：install/upload/uninstall/status 端点 + `_post_load_setup` |
| `src/qwenpaw/plugins/loader.py` | PluginLoader：`load_plugin_from_path`、`_install_requirements`、`_find_uv` |
| `src/qwenpaw/app/_app.py` (284-288行) | app.state 初始化：plugin_loader、provider_manager 等 |
| `src/qwenpaw/app/utils.py` (92-129行) | `schedule_agent_reload` — 非阻塞后台重载 |
| `src/qwenpaw/app/runner/task_tracker.py` | 现成的 TaskTracker（per-workspace，不适用于全局插件安装） |
| `console/src/api/modules/plugin.ts` | 前端 API：installPlugin、uploadPlugin、fetchPluginStatus |
| `console/src/pages/Settings/PluginManager/hooks/useInstallModal.ts` | 手动安装弹窗逻辑 |
| `console/src/pages/Settings/PluginManager/hooks/useOfficialPlugins.ts` | 官方插件安装逻辑 |

### 关键发现

1. `TaskTracker` 是 per-workspace 的，不适合全局插件安装追踪 → 需要新建全局 `PluginInstallTracker`
2. `_post_load_setup` 依赖 `request.app.state` 中的 loader/provider_manager/multi_agent_manager → 需重构为接受独立对象
3. `schedule_agent_reload` 已经是非阻塞的（`asyncio.create_task`），后台调用安全
4. ZIP 上传的临时文件问题：在返回 task_id 前同步完成解压和复制，后台只做 pip install + load
5. `app/plugins/` 目录尚不存在，需新建
6. 前端无现成的通用轮询 hook，但 MCP OAuth 组件有 `setInterval(2000ms)` 轮询模式可参考

## 实施步骤

### 步骤 1：后端基础 — PluginInstallTracker

创建 `src/qwenpaw/app/plugins/__init__.py`（空文件，使目录成为包）。

创建 `src/qwenpaw/app/plugins/install_tracker.py`，包含：

```python
class PluginInstallTracker:
    # 用 asyncio.Lock 保护的 dict[str, dict]
    # 状态: pending -> running -> completed | failed
    # stage 子状态: installing_deps, loading, setting_up
    # 方法: create_task, update_task, get_task
    # 新任务创建时清理超过3600s的旧任务
```

在 `src/qwenpaw/app/_app.py` 第287行附近添加：
```python
from .plugins.install_tracker import PluginInstallTracker
app.state.plugin_install_tracker = PluginInstallTracker()
```

### 步骤 2：后端 API — 重构 plugins.py

1. 添加 `import uuid`
2. 重构 `_post_load_setup(request, plugin_id)` → `_post_load_setup_async(loader, provider_manager, multi_agent_manager, plugin_id)` — 接受独立对象
3. 重构 `_schedule_all_agents_reload(request)` → 接受 `multi_agent_manager` 参数
4. 新增 `_run_install_background()` — 后台执行 pip install → load_plugin → _post_load_setup_async，异常捕获后更新 tracker
5. `install_plugin` 端点改造：
   - 同步完成：下载/解压/复制文件到插件目录、卸载旧版本（force时）
   - 生成 `task_id = str(uuid.uuid4())`
   - 注册到 tracker
   - `asyncio.create_task(_run_install_background(...))`
   - 返回 `{task_id, status: "pending"}`
6. `upload_plugin` 端点同样模式
7. 新增 `GET /plugins/install/{task_id}/status` 端点

### 步骤 3：前端 API 层 — plugin.ts

```typescript
export interface InstallTask {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  stage?: string;
  plugin_id?: string;
  error?: string;
  result?: InstallPluginResult;
}

// installPlugin/uploadPlugin 返回类型改为:
Promise<{task_id: string; status: string}>

// 新增:
export async function fetchInstallStatus(taskId: string): Promise<InstallTask>
```

### 步骤 4：前端 UI — 两个 hooks

**useInstallModal.ts**：
- 删除 `localInstalling`/`urlInstalling` 状态
- 新增 `installTaskId: string | null` 状态
- 新增 `useEffect` 轮询：`setInterval(2000ms)`，最多 180 次（360s 超时，比 pip 的 300s 多 60s 缓冲）
- 轮询中：status=completed → 显示成功 + 刷新页面；status=failed → 显示错误

**useOfficialPlugins.ts**：
- 删除 `installingId` 状态，同样改为 `installTaskId` + 轮询

## 验证方式

1. `./scripts/dev.sh` 启动后端
2. `cd console && npm run dev` 启动前端
3. Settings → Plugin Manager → 安装官方插件
4. 确认按钮显示进度文字而非永久卡住
5. 确认成功/失败都能正确显示并恢复 UI
6. 测试 ZIP 上传安装同样正常
7. `pytest tests/ -v -k plugin` 确认无回归

## 未解决的问题

- 服务器重启时正在进行的安装任务会丢失（内存中的 tracker 被清空）。v1 可接受，下次启动时 `load_all_plugins` 会尝试加载已复制的插件文件。
- 两个同时安装同一插件的请求：第二个会因为 `plugin_id in self._loaded_plugins` 检查而被拒绝，不会冲突。