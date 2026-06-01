# GitHub Trend Hub

使用 GitHub Trend Hub 插件管理热榜数据、订阅仓库、生成分析报告。

## 触发场景

- "查看今日热榜"、"获取 GitHub Trending"
- "订阅 xxx 仓库"、"监控 xxx 项目"
- "上传热榜数据"、"上传监控数据"
- "生成热榜分析报告"
- "搜索 GitHub 仓库趋势"

## 工作原理

```
Agent 采集数据（爬虫/API）
    ↓
调用 Skill 中的 HTTP 请求上传数据
    ↓
github-trending 后端存储（SQLite）
    ↓
前端页面展示
```

## 基础信息

- **后端地址**: `http://127.0.0.1:7901`
- **插件目录**: `/home/hr/.qwenpaw/plugins/github-trending/`

---

## 热榜数据管理

### 上传热榜数据

```python
import httpx

async def upload_trending():
    data = {
        "date": "2026-05-30",  # 可选，默认今天
        "language": "all",      # 可选，all/python/go 等
        "summary": "今日趋势：AI视频生成类项目热度上升",
        "items": [
            {
                "rank": 1,
                "name": "MoneyPrinterTurbo",
                "owner": "harry0703",
                "full_name": "harry0703/MoneyPrinterTurbo",
                "description": "利用AI大模型，一键生成高清短视频",
                "language": "Python",
                "stars": 72507,
                "stars_delta": 3567,
                "forks": 10160,
                "url": "https://github.com/harry0703/MoneyPrinterTurbo",
                "analysis": "这个项目是..."
            }
        ]
    }
    resp = httpx.post(f"{BASE_URL}/trending/upload", json=data)
    return resp.json()
```

### 获取热榜数据

```python
async def get_daily_trending(date: str = None, language: str = "all"):
    """获取某天热榜，默认今天"""
    resp = httpx.get(
        f"{BASE_URL}/trending/daily",
        params={"date": date, "language": language}
    )
    return resp.json()

async def get_available_dates(language: str = "all"):
    """获取有数据的日期列表"""
    resp = httpx.get(f"{BASE_URL}/trending/dates", params={"language": language})
    return resp.json()
```

---

## 仓库管理

### 搜索项目

```python
async def search_repos(keyword: str, limit: int = 20):
    resp = httpx.get(
        f"{BASE_URL}/repos/search",
        params={"keyword": keyword, "limit": limit}
    )
    return resp.json()
```

### 获取项目详情

```python
async def get_repo_detail(full_name: str):
    """full_name 格式: owner/repo"""
    resp = httpx.get(f"{BASE_URL}/repos/{full_name}")
    return resp.json()

async def get_repo_trend(full_name: str):
    """获取项目历史趋势"""
    resp = httpx.get(f"{BASE_URL}/repos/{full_name}/trend")
    return resp.json()
```

---

## 订阅监控

### 管理订阅

```python
async def list_subscriptions():
    resp = httpx.get(f"{BASE_URL}/monitor/subscriptions")
    return resp.json()

async def add_subscription(repo: str):
    """订阅一个仓库，格式: owner/repo"""
    resp = httpx.post(f"{BASE_URL}/monitor/subscriptions", params={"target": repo})
    return resp.json()

async def delete_subscription(subscription_id: int):
    resp = httpx.delete(f"{BASE_URL}/monitor/subscriptions/{subscription_id}")
    return resp.json()
```

### 上传监控数据

```python
async def upload_monitor_events(repo: str, repo_info: dict, events: list):
    data = {
        "repo": repo,
        "repo_info": {
            "stars": 72507,
            "forks": 10160,
            "open_issues": 12,
            "language": "Python",
            "description": "项目描述",
            "last_commit": "2小时前"
        },
        "events": [
            {
                "type": "release",      # release/commit/star_update/issue
                "title": "v2.3.0 发布",
                "body": "新增多语言字幕支持",
                "version": "v2.3.0",
                "url": "https://github.com/...",
                "time": "2026-05-29T10:00:00Z"
            }
        ]
    }
    resp = httpx.post(f"{BASE_URL}/monitor/upload", json=data)
    return resp.json()

async def get_monitor_events(repo: str = None, limit: int = 50):
    resp = httpx.get(
        f"{BASE_URL}/monitor/events",
        params={"repo": repo, "limit": limit}
    )
    return resp.json()
```

---

## 分析报告

### 上传报告

```python
async def upload_report(date: str, report_type: str, content: dict, source: str = "llm"):
    data = {
        "date": date,
        "type": report_type,  # daily_report/special_report
        "source": source,     # llm/manual
        "content": {
            "overview": "今日共 156 个项目上榜...",
            "highlights": [
                {"project": "MoneyPrinterTurbo", "insight": "AI视频生成赛道持续火爆"}
            ],
            "trends": ["AI 视频生成类项目热度持续上升"],
            "suggestions": ["关注 AI + 视频 + 自动化 交叉领域"]
        }
    }
    resp = httpx.post(f"{BASE_URL}/reports", json=data)
    return resp.json()

async def get_reports(date: str = None, limit: int = 30):
    resp = httpx.get(f"{BASE_URL}/reports", params={"date": date, "limit": limit})
    return resp.json()
```

---

## 典型工作流

### 1. 定时采集热榜

```python
# 1. 爬取 GitHub Trending 页面
# 2. 整理数据格式
# 3. 上传到插件存储
await upload_trending(date="2026-05-30", items=[...])

# 4. 调用 LLM 生成分析
analysis = await llm.analyze(trending_data)

# 5. 上传分析报告
await upload_report(date="2026-05-30", content=analysis)
```

### 2. 订阅监控仓库

```python
# 1. 添加订阅
await add_subscription("harry0703/MoneyPrinterTurbo")

# 2. 定时调用 GitHub API 获取动态
# 3. 上传监控数据
await upload_monitor_events(repo="harry0703/MoneyPrinterTurbo", repo_info={...}, events=[...])

# 4. 查询动态
events = await get_monitor_events(repo="harry0703/MoneyPrinterTurbo")
```

---

## 注意事项

1. **Base URL**: `http://127.0.0.1:7901`（插件后端端口固定 7901）
2. **异步调用**: 所有 API 都是异步的，使用 `httpx.AsyncClient`
3. **数据格式**: 上传前确保字段完整，特别是 `full_name` 格式为 `owner/repo`
4. **日期格式**: 使用 `YYYY-MM-DD` 格式

## ⚠️ 依赖安装 BOM 问题

`requirements.txt` 文件开头包含 UTF-8 BOM（`﻿`），如果用编辑器保存时未正确处理，会导致第一行依赖（`fastapi`）在插件加载时被静默跳过，进而触发不必要的依赖安装或插件加载失败。

**症状**: 插件反复尝试安装依赖，或提示 "Plugin loader is not ready yet"。

**原因**: `str.strip()` 无法删除 BOM 字符（`﻿`），导致 `Requirement('﻿fastapi==...')` 解析失败后被静默忽略。

**修复方式**: 用纯文本编辑器（如 VS Code）重新保存 `requirements.txt` 为 UTF-8 无 BOM 格式，或手动删除文件首部的 `﻿` 字符。
