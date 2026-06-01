# GitHub Trending 人用化改造 - 设计文档

**版本**：1.0.0
**日期**：2026-06-01
**状态**：已批准
**插件**：`plugins/bundle/github-trending`

---

## 1. 概述

把 `github-trending` 从"AI 工具附属"改造为**人 + AI 双通道可用**的 GitHub 热榜数据平台。
继承 Mode A 架构（路由挂主进程），参考 `/opt/github/github-data-fetch` 的暗色主题与侧边日期 + 右侧表格布局。

### 1.1 目标

| 目标 | 衡量 |
|------|------|
| 人可配置采集频率、立即触发 | 设置页可改 interval/语言/周期,点按钮立即跑一轮 |
| 数据全可检索 | `repos` 表 + 现有 `/repos/search` 接口 |
| 订阅真监控 | 订阅 repo stars 变化、新进 trending 项目都写 `monitor_events` |
| 所有接口真可用 | 修 BASE_URL 硬编码、所有 12 个工具可用 |
| UI 风格统一 | 暗色 + 青色 accent,跟 github-data-fetch 同款 |

### 1.2 约束

- Mode A 架构：路由直接挂 QwenPaw 主进程（8088），不启子进程
- 前端用 host 提供的 `antd`,无法用 ConfigProvider,深色靠 CSS 变量 + inline style
- 不引入 GitHub Token,所有抓取走 GitHub HTML
- 写操作只走前端,AI 工具只暴露只读接口

---

## 2. 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | FastAPI（已用）+ aiosqlite + httpx + BeautifulSoup |
| 前端 | React + TypeScript + Ant Design（host 提供） |
| 调度 | 主进程内 asyncio Task,无独立 worker |
| 数据 | SQLite,`~/.qwenpaw/data/github-trending.db` |

---

## 3. 数据模型

### 3.1 复用现有表（7 张）

`daily_trending` / `repos` / `repo_history` / `subscriptions` / `monitor_events` / `watched_repos` / `reports`,schema 不变。

### 3.2 新增表

#### `settings` — 运行时配置
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
存：`collect_enabled` / `collect_interval_min` / `collect_period` / `collect_languages`(JSON 数组)。

#### `repo_watch_log` — 订阅 repo 详情快照
```sql
CREATE TABLE repo_watch_log (
    subscription_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    language TEXT,
    description TEXT,
    last_checked_at DATETIME,
    PRIMARY KEY (subscription_id, full_name),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
);
```

### 3.3 不变表

- `repos.appearances` 字段已存在,继续累加
- `monitor_events.event_type` 已支持 `star_update` / `trending_new` / `collector_error` 几种字符串值

---

## 4. 后端改动

### 4.1 新文件

#### `app/settings.py` — 运行时配置
- `get_runtime_settings() -> dict` — 读 DB,fallback env,cache 60 秒
- `set_runtime_setting(key, value)` — 写 DB + 清缓存
- `get_setting(key, default=None)` — 单 key 读取
- 类型：bool / int / str / list,按 key 名字典查类型

#### `app/monitor_refresh.py` — 订阅 repo 刷新
- `refresh_one_repo(full_name) -> dict` — httpx 拉 `github.com/{owner}/{repo}`,BeautifulSoup 解析 stars/forks/language/description/last_commit,与 `repo_watch_log` diff
  - 首次拉取：写 watch_log,不发事件
  - stars 变化 ≥5 写 `monitor_events(type=star_update, body="stars: 1000 → 1050")`
  - language / description 变化也写一条 `repo_meta_update`
- `refresh_all_subscribed_repos() -> dict` — 并行拉（asyncio.Semaphore(5)）,汇总结果
- `record_watch_log(subscription_id, full_name, info)` — 写 / 更新 watch_log

#### `app/trending_diff.py` — 趋势增量检测
- `detect_new_entries(today, yesterday) -> list[dict]` — 对比两天 `daily_trending.data` items,full_name 不在昨天的写进列表
- `record_new_entries(entries, today)` — 写 `monitor_events(type=trending_new)` 到 `github-trending-collector` 伪仓库（沿用现有错误回写模式）

#### `app/routers/settings.py` — 设置路由
- `GET /settings` — 返回当前 runtime settings
- `PUT /settings` — body: `{collect_enabled?, collect_interval_min?, collect_period?, collect_languages?}` 局部更新
- `POST /settings/trigger-collect` — 触发一次 `collect_once`,返回 `{"task_id": "...", "status": "running"}`
- `GET /settings/trigger-collect/{task_id}` — 查任务状态
- 内部维护 `_TRIGGER_TASKS: dict[str, dict]` 简单状态机

#### `app/routers/subscriptions.py` — 订阅路由（部分重写）
- 保留现有 4 个 endpoint,扩展响应字段
- `POST /subscriptions` 新增行为：写完订阅后 `asyncio.create_task(refresh_one_repo(...))` 立刻拉一次
- `GET /subscriptions` 返回字段加：`last_checked_at` / `current_stars` / `current_forks`（LEFT JOIN watch_log）
- `GET /events` 保留,加可选 `event_type` 过滤

### 4.2 修改文件

#### `app/collector.py`
- 顶部 `from app.config import settings` 改为 `from app.settings import get_runtime_settings`
- `collect_once` 入口读 runtime settings,不再读 env
- `run_collector_loop` 每轮结束（成功 / 失败都走）后 `asyncio.create_task(refresh_all_subscribed_repos())` + `detect_new_entries` 并行触发
- 间隔变更支持：每轮重新读 `collect_interval_min`,变长 / 变短都自适应（不等满当前 interval）

#### `app/database.py`
- `init_db()` 新增 2 张表 + 索引
- 新增函数：`get_setting(key)` / `set_setting(key, value)` / `list_settings()` / `get_watch_log(sub_id, full_name)` / `upsert_watch_log(...)` / `list_watch_logs(sub_id)`

#### `app/routers/__init__.py`
- `register_routers` 加 `settings_router` prefix="/settings"

#### `plugin.py`
- `import settings_router`
- `register_http_router(settings_router, prefix="/settings", tags=["github-trending"])`
- 工具注册改为只注册 8 个只读工具,删 `trending_upload` / `report_upload` / `monitor_subscribe` / `monitor_unsubscribe` / `monitor_upload` / `trending_get_dates`(都通过前端)

#### `tools/*.py`
- 全部文件 `BASE_URL` 改为：
  ```python
  import os
  BASE_URL = os.environ.get("QWENPAW_TOOL_BASE_URL", "http://127.0.0.1:8088")
  ```
  加注释说明：Mode A 下,路由在主进程,默认 8088 端口;可通过 env 覆盖
- 删 4 个写工具(原 `trending.py` / `reports.py` / `monitor.py` 中只保留读函数)
- `__init__.py` 留空,不再 export

### 4.3 配置参数（runtime settings）

| key | 类型 | 默认 | UI 控件 |
|-----|------|------|---------|
| `collect_enabled` | bool | true | Switch |
| `collect_interval_min` | int | 60 | InputNumber + 预设 chip |
| `collect_period` | str | "daily" | Radio(daily/weekly/monthly) |
| `collect_languages` | list[str] | ["", "python", "go", "rust", ...] | Select(multiple)+ 自定义输入 |

`stars_change_threshold`(硬编码 5)与 `repo_refresh_concurrency`(硬编码 5)不暴露。

---

## 5. 前端改动

### 5.1 主题注入

`frontend/src/index.tsx` 顶部插入 `<style>` 块定义 CSS 变量(只对插件根容器生效),参考 github-data-fetch:

```css
.gh-trending-root {
  --gh-bg: #0A0D14;
  --gh-card: #171D2A;
  --gh-elevated: #222A3E;
  --gh-border: #262F42;
  --gh-text: #E4EAF0;
  --gh-text-secondary: #8892A8;
  --gh-text-tertiary: #5A6478;
  --gh-accent: #00D4AA;
  --gh-accent-glow: rgba(0, 212, 170, 0.2);
  --gh-radius: 10px;
  font-family: 'DM Sans', system-ui, sans-serif;
}
```

外层 App 包一个 `<div class="gh-trending-root">`。

### 5.2 页面改动

| 页面 | 改动 |
|------|------|
| `index.tsx` | 5 个 Tab(原 4 + ⚙️ 设置);根 div 加 className |
| `TrendingPage.tsx` | 重写:180px 日期侧栏 + 表格(rank/仓库/语言/stars/今日涨/订阅按钮);hover 高亮 |
| `ReposPage.tsx` | 重写:搜索 + 表格 + drawer 详情 |
| `MonitorPage.tsx` | 重写:订阅卡片 + 动态流;事件按 type 染色 |
| `ReportsPage.tsx` | 表格化列表 + drawer 详情 |
| `SettingsPage.tsx`(**新**) | 见 5.3 |

### 5.3 Settings 页设计

```
┌──────────────────────────────────────────────────┐
│ ⚙️ 采集设置                                        │
│                                                    │
│ ┌─ 启用采集 ──────────────────── [●════] 启用 ──┐ │
│                                                  │
│ ┌─ 采集频率 ─────────────────────────────────┐   │
│ │  [ 60 ] 分钟                                │   │
│ │  预设: [30] [60] [180] [360] [720] [1440]   │   │
│ └────────────────────────────────────────────┘   │
│                                                  │
│ ┌─ 周期 ─ (•) daily  ( ) weekly  ( ) monthly ┐ │
│                                                  │
│ ┌─ 抓取语言 ──────────────────────────────┐    │
│ │  全部 / Python / Go / Rust / TypeScript    │    │
│ │  JavaScript / Java / HTML / C++           │    │
│ │  [ + 自定义: ___________ ]                │    │
│ └────────────────────────────────────────────┘   │
│                                                  │
│ ┌─ 状态 ─────────────────────────────────────┐  │
│ │  上次运行: 2026-06-01 22:00:00              │  │
│ │  上次结果: ✅ 8 种语言  ❌ 0 失败             │  │
│ │  下次运行: 2026-06-01 23:00:00              │  │
│ └────────────────────────────────────────────┘   │
│                                                  │
│ [🚀 立即采集一次]   [💾 保存设置]                   │
└──────────────────────────────────────────────────┘
```

- 改频率即时写入（无需 Save）
- 「立即采集」点完 disabled,30 秒轮询状态

### 5.4 路由结构（host `registerRoutes` 不变）

```
/plugin/github-trending  → App(5 tabs)
  trending  repos  monitor  reports  settings
```

---

## 6. 数据流

### 6.1 配置变更流
```
用户改频率 (UI) → PUT /settings
  → settings 表 UPSERT key=value
  → 清 runtime cache
  → 下次 collector tick 读新值
```

### 6.2 手动触发流
```
用户点 [🚀 立即采集]
  → POST /settings/trigger-collect
  → 后端 asyncio.create_task(collect_once())
  → 返回 task_id
  → 前端 30s 轮询 GET /settings/trigger-collect/{task_id}
  → 完成后 message.success 显示结果
```

### 6.3 订阅监控流
```
collector 一轮抓取完成
  ├─→ detect_new_entries()       → monitor_events (trending_new)
  └─→ refresh_all_subscribed_repos() (5 并发)
         每个 repo: refresh_one_repo(full_name)
           → httpx 拉 github.com/owner/repo
           → bs4 解析
           → diff repo_watch_log
           → stars 变 ≥5: monitor_events (star_update)
           → language/desc 变: monitor_events (repo_meta_update)
           → UPSERT repo_watch_log
```

### 6.4 订阅新建流
```
用户点 [+ 添加订阅] 输入 owner/repo
  → POST /monitor/subscriptions
  → DB 写 subscriptions
  → asyncio.create_task(refresh_one_repo(...))
  → 前端 message.success
```

---

## 7. AI 工具面（只读）

| Tool | 函数 | 端点 |
|------|------|------|
| `trending_get_daily` | `trending.py:trending_get_daily` | GET /trending/daily |
| `trending_get_dates` | `trending.py:trending_get_dates` | GET /trending/dates |
| `repo_search` | `repos.py:repo_search` | GET /repos/search |
| `repo_detail` | `repos.py:repo_detail` | GET /repos/{full_name} |
| `repo_trend` | `repos.py:repo_trend` | GET /repos/{full_name}/trend |
| `monitor_list_subscriptions` | `monitor.py:monitor_list_subscriptions` | GET /monitor/subscriptions |
| `monitor_get_events` | `monitor.py:monitor_get_events` | GET /monitor/events |
| `report_list` | `reports.py:report_list` | GET /reports |

移除的写工具(从 `plugin.py` `register_tool` 删):
- `trending_upload`(原 `tools/trending.py:trending_upload`)
- `report_upload`(原 `tools/reports.py:report_upload`)
- `monitor_subscribe` / `monitor_unsubscribe` / `monitor_upload`(原 `tools/monitor.py`)

保留的只读工具 8 个(全部注册到 Agent,见上表)。`tools/*.py` 文件不删,只删对应写函数 + 不再 import。

---

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| settings DB 读失败 | 降级用 env 默认值,记 warn log |
| 手动触发 collect 时已有 collect 在跑 | 拒绝,返回 409 + 提示 |
| refresh_one_repo 单 repo 失败 | 写 `monitor_events(type=refresh_error, repo=...)` 不影响其他 |
| 5 并发全失败 | 记 `monitor_events(type=batch_refresh_failed)`,不发崩溃 |
| GitHub 限流(429) | 立即停止本轮 refresh,sleep 60s 后重试单 repo,失败则跳过 |
| 前端 PUT /settings 字段类型错 | 后端 422 + 详细错误,前端 message.error |
| 手动触发任务 5 分钟没完成 | 后端标记 timeout,前端轮询显示 |

---

## 9. 测试

### 9.1 后端单测（pytest）
- `test_settings.py`：DB CRUD + cache
- `test_monitor_refresh.py`：mock httpx,测 diff 逻辑
- `test_trending_diff.py`：mock DB,测 new entries 检测
- `test_collector.py`：mock runtime settings,测 collect_once 完整路径
- `test_routers_settings.py`：FastAPI TestClient

### 9.2 手工验收
- 改频率后 1 分钟内下次 tick 用新值
- 手动触发 → 30s 内看到结果
- 订阅一个 repo → 5s 内 watch_log 有数据
- 改 repo stars 模拟（手动 SQL 改 watch_log）→ 下次 collector 跑完看到 star_update 事件
- 前端 5 个 tab 切换正常
- AI agent 调 8 个只读工具都返回数据

---

## 10. 不做的事（YAGNI）

- ❌ 多用户配置（当前是单租户）
- ❌ GitHub Token 接入（保持纯 HTML 抓取）
- ❌ 邮件 / 飞书 / 钉钉通知（事件只入库,通知另开插件）
- ❌ 复杂的 cron 表达式（全局 interval 够用）
- ❌ 国际化 i18n（中文界面）
- ❌ 报告内容生成（只存用户 / AI 上传的报告）
- ❌ 收藏 / 标签 / 笔记（GitHub 自带 star）
- ❌ WebSocket 推送（前端轮询够用）

---

## 11. 风险与回滚

| 风险 | 缓解 |
|------|------|
| settings 表破坏现有数据 | 新表,旧 7 张表 schema 不动 |
| BASE_URL 改 env 影响其它插件 | 改的是 github-trending 自己 tools/*.py,作用域隔离 |
| 移除注册工具破坏已有 Agent 流程 | 删除的是写工具;只读工具 Agent 极少调;回滚 = 加回 register_tool 即可 |
| 频繁刷新订阅 repo 触发 GitHub 限流 | 并发 5 + 间隔 3s,远低于 GitHub 阈值 |
| collector + repo refresh 双跑耗时 | 走 `asyncio.create_task` 并行,不阻塞 trending 写库 |

---

## 12. 文件清单

### 新建
- `app/settings.py`
- `app/monitor_refresh.py`
- `app/trending_diff.py`
- `app/routers/settings.py`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/styles.ts`（CSS 变量常量）

### 修改
- `app/database.py`
- `app/collector.py`
- `app/routers/__init__.py`
- `app/routers/subscriptions.py`(原 monitor.py router)
- `plugin.py`
- `tools/trending.py` / `tools/reports.py` / `tools/monitor.py` / `tools/repos.py` / `tools/__init__.py`
- `frontend/src/index.tsx`
- `frontend/src/pages/TrendingPage.tsx` / `ReposPage.tsx` / `MonitorPage.tsx` / `ReportsPage.tsx`
- `frontend/src/utils.ts`（加暗色相关 helper）
