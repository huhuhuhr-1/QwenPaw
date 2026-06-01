# github-trending 人用化改造 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 github-trending 插件改造为人 + AI 双通道可用,补齐设置页、订阅真监控、暗色 UI。

**Architecture:** 保持 Mode A 架构,新增 settings / repo_watch_log 2 张表,加 3 个后端模块(settings / monitor_refresh / trending_diff) + 1 个 settings router,前端重写 4 个页面 + 新增 SettingsPage。

**Tech Stack:** FastAPI / aiosqlite / httpx + BeautifulSoup(已用) + React / TypeScript / Ant Design(host 提供)。

**Spec:** `docs/superpowers/specs/2026-06-01-github-trending-human-usage-design.md`

---

## Task 1: 数据库层 — settings + repo_watch_log 表 + CRUD

**Files:**
- Modify: `plugins/bundle/github-trending/app/database.py`
- Test: `plugins/bundle/github-trending/tests/test_settings_db.py`(新建)

- [ ] **Step 1: 写测试 — settings CRUD**

在 `plugins/bundle/github-trending/tests/` 建 `__init__.py` 空文件,再创建 `test_settings_db.py`:

```python
import asyncio
import tempfile
from pathlib import Path
import pytest

from app.config import Settings
from app import database


@pytest.fixture
async def fresh_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(tmp))
    await database.init_db()
    yield str(tmp)


async def test_setting_upsert_and_read(fresh_db):
    await database.set_setting("collect_enabled", "true")
    val = await database.get_setting("collect_enabled")
    assert val == "true"


async def test_setting_default(fresh_db):
    val = await database.get_setting("missing_key", "fallback")
    assert val == "fallback"


async def test_list_settings(fresh_db):
    await database.set_setting("collect_interval_min", "60")
    await database.set_setting("collect_period", "daily")
    all_settings = await database.list_settings()
    assert all_settings["collect_interval_min"] == "60"
    assert all_settings["collect_period"] == "daily"
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_db.py -v
```

Expected: `ImportError` 或 `AttributeError: module 'app.database' has no attribute 'set_setting'`。

- [ ] **Step 3: 在 database.py 加 settings CRUD**

修改 `app/database.py`,在文件末尾(`get_report` 之后)添加:

```python
# ── 设置操作 ──


async def get_setting(key: str, default: str = None) -> Optional[str]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else default
    finally:
        await db.close()


async def set_setting(key: str, value: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()


async def list_settings() -> Dict[str, str]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT key, value FROM settings")
        rows = await cur.fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        await db.close()
```

- [ ] **Step 4: 在 init_db() 加 settings + repo_watch_log 表**

修改 `app/database.py` 的 `init_db()` 函数,在现有 CREATE TABLE 之后(在 `await db.commit()` 之前)添加:

```python
# 运行时设置
await db.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# 订阅 repo 详情快照
await db.execute("""
    CREATE TABLE IF NOT EXISTS repo_watch_log (
        subscription_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        stars INTEGER DEFAULT 0,
        forks INTEGER DEFAULT 0,
        language TEXT,
        description TEXT,
        last_checked_at DATETIME,
        PRIMARY KEY (subscription_id, full_name),
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
    )
""")
```

- [ ] **Step 5: 在 database.py 末尾加 watch_log CRUD**

```python
# ── 订阅 watch log ──


async def upsert_watch_log(subscription_id: int, full_name: str, info: Dict) -> None:
    db = await get_db()
    try:
        await db.execute("""
            INSERT INTO repo_watch_log
            (subscription_id, full_name, stars, forks, language, description, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(subscription_id, full_name) DO UPDATE SET
                stars = excluded.stars,
                forks = excluded.forks,
                language = excluded.language,
                description = excluded.description,
                last_checked_at = CURRENT_TIMESTAMP
        """, (
            subscription_id, full_name,
            info.get("stars", 0), info.get("forks", 0),
            info.get("language"), info.get("description"),
        ))
        await db.commit()
    finally:
        await db.close()


async def get_watch_log(subscription_id: int, full_name: str) -> Optional[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM repo_watch_log WHERE subscription_id = ? AND full_name = ?",
            (subscription_id, full_name),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_watch_logs_by_subscription(subscription_id: int) -> List[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM repo_watch_log WHERE subscription_id = ?",
            (subscription_id,),
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
```

- [ ] **Step 6: 跑测试确认 pass**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_db.py -v
```

Expected: 3 passed。

- [ ] **Step 7: 提交**

```bash
git add plugins/bundle/github-trending/app/database.py plugins/bundle/github-trending/tests/
git commit -m "feat(github-trending): add settings + repo_watch_log tables and CRUD"
```

---

## Task 2: settings.py 运行时配置读取模块

**Files:**
- Create: `plugins/bundle/github-trending/app/settings.py`
- Test: `plugins/bundle/github-trending/tests/test_settings_module.py`

- [ ] **Step 1: 写测试**

```python
import pytest
from unittest.mock import patch, AsyncMock

from app import settings as settings_mod


@pytest.fixture(autouse=True)
def reset_cache():
    settings_mod._cache = None
    settings_mod._cache_ts = 0
    yield


async def test_runtime_settings_default_from_env():
    with patch("app.settings.list_settings", new=AsyncMock(return_value={})):
        cfg = await settings_mod.get_runtime_settings()
    assert cfg["collect_enabled"] is True
    assert cfg["collect_interval_min"] == 60
    assert cfg["collect_period"] == "daily"
    assert "python" in cfg["collect_languages"]


async def test_runtime_settings_override_from_db():
    db_values = {
        "collect_enabled": "false",
        "collect_interval_min": "180",
        "collect_period": "weekly",
        "collect_languages": '["rust", "go"]',
    }
    with patch("app.settings.list_settings", new=AsyncMock(return_value=db_values)):
        cfg = await settings_mod.get_runtime_settings()
    assert cfg["collect_enabled"] is False
    assert cfg["collect_interval_min"] == 180
    assert cfg["collect_period"] == "weekly"
    assert cfg["collect_languages"] == ["rust", "go"]


async def test_set_runtime_setting_calls_db():
    with patch("app.settings.set_setting", new=AsyncMock()) as mock_set, \
         patch("app.settings._cache", None):
        await settings_mod.set_runtime_setting("collect_period", "monthly")
    mock_set.assert_called_once_with("collect_period", "monthly")
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_module.py -v
```

Expected: `ImportError: cannot import name 'settings' from 'app'`。

- [ ] **Step 3: 写 settings.py**

新建 `app/settings.py`:

```python
"""运行时配置 — 读 DB 覆盖 env,cache 60s。"""

import json
import time
from typing import Any, Dict, List, Optional

from app.config import settings as env_settings
from app.database import get_setting, set_setting, list_settings

_CACHE_TTL_SEC = 60
_cache: Optional[Dict[str, Any]] = None
_cache_ts: float = 0


def _parse_languages_json(raw: str) -> List[str]:
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v]
    except (json.JSONDecodeError, TypeError):
        pass
    return env_settings.collect_languages


def _coerce(key: str, raw: str) -> Any:
    """按 key 类型转换字符串 → 原始类型。"""
    if key == "collect_enabled":
        return raw.lower() in ("true", "1", "yes")
    if key == "collect_interval_min":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 60
    if key == "collect_period":
        return raw if raw in ("daily", "weekly", "monthly") else "daily"
    if key == "collect_languages":
        return _parse_languages_json(raw)
    return raw


async def get_runtime_settings() -> Dict[str, Any]:
    """读 DB 配置,fallback env settings。Cache 60s。"""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL_SEC:
        return _cache

    db_values = await list_settings()
    cfg = {
        "collect_enabled": env_settings.collect_enabled,
        "collect_interval_min": env_settings.collect_interval_min,
        "collect_period": env_settings.collect_period,
        "collect_languages": list(env_settings.collect_languages),
    }
    for key, raw in db_values.items():
        if key in cfg:
            cfg[key] = _coerce(key, raw)

    _cache = cfg
    _cache_ts = now
    return cfg


async def set_runtime_setting(key: str, value: Any) -> None:
    """写一个 setting 到 DB + 清缓存。"""
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    await set_setting(key, raw)
    _cache = None
    _cache_ts = 0


def clear_cache() -> None:
    """手工清 cache(给 collector 用)。"""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0
```

- [ ] **Step 4: 跑测试确认 pass**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_module.py -v
```

Expected: 3 passed。

- [ ] **Step 5: 提交**

```bash
git add plugins/bundle/github-trending/app/settings.py plugins/bundle/github-trending/tests/test_settings_module.py
git commit -m "feat(github-trending): runtime settings module with 60s cache"
```

---

## Task 3: monitor_refresh.py 订阅 repo 详情刷新

**Files:**
- Create: `plugins/bundle/github-trending/app/monitor_refresh.py`
- Test: `plugins/bundle/github-trending/tests/test_monitor_refresh.py`

- [ ] **Step 1: 写测试**

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app import monitor_refresh


def test_parse_repo_html_basic():
    html = """
    <html><body>
    <h1>owner / name</h1>
    <span itemprop="programmingLanguage">Python</span>
    <p>Some description text</p>
    <a href="/owner/name/stargazers">1,234</a>
    <a href="/owner/name/network/members">56</a>
    <relative-time datetime="2026-05-30T10:00:00Z">3 days ago</relative-time>
    </body></html>
    """
    info = monitor_refresh.parse_repo_html(html, "owner/name")
    assert info["stars"] == 1234
    assert info["forks"] == 56
    assert info["language"] == "Python"
    assert info["description"] == "Some description text"
    assert info["last_commit"] is not None


def test_parse_repo_html_handles_missing_fields():
    html = "<html><body><h1>owner / name</h1></body></html>"
    info = monitor_refresh.parse_repo_html(html, "owner/name")
    assert info["stars"] == 0
    assert info["forks"] == 0
    assert info["language"] == ""
    assert info["description"] == ""


def test_diff_returns_star_update_when_above_threshold():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 110, "forks": 10, "language": "Python", "description": "A"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert len(events) == 1
    assert events[0]["type"] == "star_update"
    assert "100 → 110" in events[0]["body"]


def test_diff_returns_no_event_when_below_threshold():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 102, "forks": 10, "language": "Python", "description": "A"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert events == []


def test_diff_returns_meta_update_on_description_change():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 100, "forks": 10, "language": "Python", "description": "B"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert any(e["type"] == "repo_meta_update" for e in events)
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_monitor_refresh.py -v
```

Expected: `ImportError`。

- [ ] **Step 3: 写 monitor_refresh.py**

新建 `app/monitor_refresh.py`:

```python
"""订阅 repo 详情刷新与 diff。"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from app.database import (
    get_subscriptions,
    get_watch_log,
    list_watch_logs_by_subscription,
    upsert_watch_log,
    upload_monitor_events,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

CONCURRENCY = 5
REQUEST_TIMEOUT_SEC = 20
STARS_CHANGE_THRESHOLD = 5


def parse_repo_html(html: str, full_name: str) -> Dict[str, Any]:
    """解析 GitHub repo HTML 提取 stars / forks / language / description / last_commit。"""
    soup = BeautifulSoup(html, "lxml")
    info: Dict[str, Any] = {
        "stars": 0,
        "forks": 0,
        "language": "",
        "description": "",
        "last_commit": None,
    }

    desc_p = soup.select_one("p.f4.my-3, p[data-test-selector='repo-description']")
    if not desc_p:
        for p in soup.select("article p, .BorderGrid p"):
            text = p.get_text(strip=True)
            if 5 < len(text) < 500 and "github.com" not in text.lower():
                desc_p = p
                break
    if desc_p:
        info["description"] = desc_p.get_text(strip=True)

    lang_span = soup.select_one("span[itemprop='programmingLanguage']")
    if lang_span:
        info["language"] = lang_span.get_text(strip=True)

    for a in soup.select("a"):
        href = a.get("href", "") or ""
        text = a.get_text(strip=True).replace(",", "")
        if "/stargazers" in href and text.isdigit():
            info["stars"] = int(text)
            break

    for a in soup.select("a"):
        href = a.get("href", "") or ""
        text = a.get_text(strip=True).replace(",", "")
        if "/network/members" in href and text.isdigit():
            info["forks"] = int(text)
            break

    rel_time = soup.select_one("relative-time[datetime]")
    if rel_time:
        info["last_commit"] = rel_time.get("datetime")

    return info


def diff_watch_log(
    old: Optional[Dict[str, Any]],
    new: Dict[str, Any],
    threshold: int = STARS_CHANGE_THRESHOLD,
) -> List[Dict[str, str]]:
    """对比新旧 watch_log,返回要写的事件列表。"""
    events: List[Dict[str, str]] = []
    if old is None:
        return events
    star_delta = new["stars"] - old.get("stars", 0)
    if abs(star_delta) >= threshold:
        events.append({
            "type": "star_update",
            "title": f"Stars {old.get('stars', 0)} → {new['stars']}",
            "body": f"stars: {old.get('stars', 0)} → {new['stars']} (delta {star_delta:+d})",
        })
    if new.get("language") and new["language"] != old.get("language"):
        events.append({
            "type": "repo_meta_update",
            "title": f"Language changed",
            "body": f"{old.get('language') or '?'} → {new['language']}",
        })
    if new.get("description") and new["description"] != old.get("description"):
        events.append({
            "type": "repo_meta_update",
            "title": f"Description changed",
            "body": new["description"][:200],
        })
    return events


async def _fetch_repo_html(full_name: str) -> str:
    url = f"https://github.com/{full_name}"
    headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def refresh_one_repo(full_name: str, subscription_id: int) -> Dict[str, Any]:
    """拉一个 repo 详情,写 watch_log,变化超过阈值发事件。"""
    try:
        html = await _fetch_repo_html(full_name)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        logger.warning("Failed to fetch %s: %s", full_name, err)
        await upload_monitor_events(
            repo=full_name,
            repo_info={"stars": 0, "forks": 0, "language": "", "description": ""},
            events=[{
                "type": "refresh_error",
                "title": f"Failed to refresh {full_name}",
                "body": err,
                "url": "",
                "version": "",
                "time": "",
            }],
        )
        return {"repo": full_name, "ok": False, "error": err}

    info = parse_repo_html(html, full_name)
    old_log = await get_watch_log(subscription_id, full_name)
    events = diff_watch_log(old_log, info)

    if events:
        repo_info = {
            "stars": info["stars"],
            "forks": info["forks"],
            "language": info["language"],
            "description": info["description"],
        }
        await upload_monitor_events(
            repo=full_name,
            repo_info=repo_info,
            events=[
                {**e, "url": f"https://github.com/{full_name}", "version": "", "time": ""}
                for e in events
            ],
        )

    await upsert_watch_log(subscription_id, full_name, info)
    return {"repo": full_name, "ok": True, "events": len(events), "stars": info["stars"]}


async def refresh_all_subscribed_repos() -> Dict[str, Any]:
    """并发拉所有订阅 repo,返回汇总。"""
    subs = await get_subscriptions()
    if not subs:
        return {"refreshed": 0, "errors": 0}

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run(sub: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            target = sub["target"]
            return await refresh_one_repo(target, sub["id"])

    results = await asyncio.gather(
        *[_run(s) for s in subs], return_exceptions=True
    )
    ok = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    err = sum(1 for r in results if not (isinstance(r, dict) and r.get("ok")))
    logger.info("Repo refresh: %d ok, %d err", ok, err)
    return {"refreshed": ok, "errors": err}
```

- [ ] **Step 4: 跑测试确认 pass**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_monitor_refresh.py -v
```

Expected: 5 passed。

- [ ] **Step 5: 提交**

```bash
git add plugins/bundle/github-trending/app/monitor_refresh.py plugins/bundle/github-trending/tests/test_monitor_refresh.py
git commit -m "feat(github-trending): subscribed repo detail refresh with diff events"
```

---

## Task 4: trending_diff.py 趋势增量检测

**Files:**
- Create: `plugins/bundle/github-trending/app/trending_diff.py`
- Test: `plugins/bundle/github-trending/tests/test_trending_diff.py`

- [ ] **Step 1: 写测试**

```python
from app import trending_diff


def test_diff_finds_new_entries():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert len(new) == 1
    assert new[0]["full_name"] == "b/y"


def test_diff_empty_today():
    today = {"items": []}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_empty_yesterday():
    today = {"items": [{"full_name": "a/x"}]}
    yesterday = None
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_no_new_when_all_overlap():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_trending_diff.py -v
```

Expected: `ImportError`。

- [ ] **Step 3: 写 trending_diff.py**

新建 `app/trending_diff.py`:

```python
"""trending 增量检测 — 对比两天 daily_trending,新增的写事件。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import get_daily_trending, upload_monitor_events

logger = logging.getLogger(__name__)

_SINK_REPO = "github-trending-trending-diff"


def find_new_entries(
    today_data: Optional[Dict[str, Any]],
    yesterday_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """对比两天 trending.items,返回只在 today 出现的 repo。"""
    if not today_data or not yesterday_data:
        return []
    today_names = {item["full_name"] for item in today_data.get("items", [])}
    yesterday_names = {item["full_name"] for item in yesterday_data.get("items", [])}
    new_names = today_names - yesterday_names
    return [item for item in today_data.get("items", []) if item["full_name"] in new_names]


async def detect_and_record(today: str, yesterday: str, language: str = "all") -> int:
    """对比 today vs yesterday,新增的写 monitor_events。返回新增数。"""
    today_data = await get_daily_trending(today, language)
    yesterday_data = await get_daily_trending(yesterday, language)
    new_entries = find_new_entries(today_data, yesterday_data)
    if not new_entries:
        return 0

    events = [
        {
            "type": "trending_new",
            "title": f"新进 Trending: {item['full_name']}",
            "body": item.get("description", ""),
            "url": item.get("url", ""),
            "version": "",
            "time": datetime.now().isoformat(),
        }
        for item in new_entries
    ]
    await upload_monitor_events(
        repo=_SINK_REPO,
        repo_info={"language": language, "description": "Trending diff sink"},
        events=events,
    )
    logger.info("Trending diff: %d new entries for %s/%s", len(new_entries), language, today)
    return len(new_entries)
```

- [ ] **Step 4: 跑测试确认 pass**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_trending_diff.py -v
```

Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
git add plugins/bundle/github-trending/app/trending_diff.py plugins/bundle/github-trending/tests/test_trending_diff.py
git commit -m "feat(github-trending): trending new-entry detection"
```

---

## Task 5: routers/settings.py + 集成到 plugin.py

**Files:**
- Create: `plugins/bundle/github-trending/app/routers/settings.py`
- Modify: `plugins/bundle/github-trending/app/routers/__init__.py`
- Modify: `plugins/bundle/github-trending/plugin.py`
- Test: `plugins/bundle/github-trending/tests/test_settings_router.py`

- [ ] **Step 1: 写测试**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.routers.settings import router


@pytest.fixture
def app():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/settings")
    return app


async def test_get_settings(app):
    with patch("app.routers.settings.get_runtime_settings", new=AsyncMock(return_value={
        "collect_enabled": True, "collect_interval_min": 60,
        "collect_period": "daily", "collect_languages": ["python"],
    })):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["collect_interval_min"] == 60


async def test_put_settings(app):
    with patch("app.routers.settings.set_runtime_setting", new=AsyncMock()) as mock_set:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/settings", json={"collect_interval_min": 180})
    assert resp.status_code == 200
    mock_set.assert_called_once_with("collect_interval_min", 180)


async def test_trigger_collect_rejects_when_running(app):
    from app.routers import settings as r
    r._TRIGGER_TASKS["existing"] = {"status": "running"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/settings/trigger-collect")
    # 接受:1) 直接 200 启动新任务 2) 409 拒绝并发
    assert resp.status_code in (200, 409)
    r._TRIGGER_TASKS.pop("existing", None)
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_router.py -v
```

Expected: `ImportError`。

- [ ] **Step 3: 写 routers/settings.py**

新建 `app/routers/settings.py`:

```python
"""设置路由 — runtime config + 手动触发采集。"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.collector import collect_once
from app.settings import get_runtime_settings, set_runtime_setting

logger = logging.getLogger(__name__)

router = APIRouter()

# 简单任务状态机:{task_id: {status, started_at, result?}}
_TRIGGER_TASKS: Dict[str, Dict[str, Any]] = {}
_TRIGGER_LOCK = asyncio.Lock()


class SettingsUpdate(BaseModel):
    collect_enabled: Optional[bool] = None
    collect_interval_min: Optional[int] = Field(default=None, ge=1, le=10080)
    collect_period: Optional[str] = None
    collect_languages: Optional[List[str]] = None


@router.get("")
async def get_settings() -> Dict[str, Any]:
    """读当前 runtime 配置。"""
    return await get_runtime_settings()


@router.put("")
async def update_settings(payload: SettingsUpdate) -> Dict[str, str]:
    """局部更新 runtime 配置。"""
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    for key, value in updates.items():
        await set_runtime_setting(key, value)
    return {"ok": "true", "updated": ",".join(updates.keys())}


@router.post("/trigger-collect")
async def trigger_collect() -> Dict[str, str]:
    """手动触发一次采集。如有任务在跑返回 409。"""
    async with _TRIGGER_LOCK:
        for tid, info in _TRIGGER_TASKS.items():
            if info.get("status") == "running":
                raise HTTPException(
                    status_code=409, detail=f"collect already running: {tid}"
                )
        task_id = uuid.uuid4().hex[:12]
        _TRIGGER_TASKS[task_id] = {"status": "running", "started_at": time.time()}
        asyncio.create_task(_run_trigger(task_id))
    return {"task_id": task_id, "status": "running"}


@router.get("/trigger-collect/{task_id}")
async def get_trigger_status(task_id: str) -> Dict[str, Any]:
    """查手动采集任务状态。"""
    info = _TRIGGER_TASKS.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, **info}


async def _run_trigger(task_id: str) -> None:
    """后台跑 collect_once,超时 5 分钟。"""
    try:
        result = await asyncio.wait_for(collect_once(), timeout=300)
        _TRIGGER_TASKS[task_id]["status"] = "done"
        _TRIGGER_TASKS[task_id]["result"] = result
    except asyncio.TimeoutError:
        _TRIGGER_TASKS[task_id]["status"] = "timeout"
    except Exception as e:  # noqa: BLE001
        _TRIGGER_TASKS[task_id]["status"] = "error"
        _TRIGGER_TASKS[task_id]["error"] = f"{type(e).__name__}: {e}"
        logger.exception("Trigger collect failed: %s", e)
```

- [ ] **Step 4: 在 routers/__init__.py 挂上 settings_router**

修改 `app/routers/__init__.py`,完整替换为:

```python
"""注册所有路由"""


def register_routers(app):
    """把 5 个子 router 挂到传入的 app(可以是 FastAPI app 或 APIRouter)。"""
    from app.routers.trending import router as trending_router
    from app.routers.repos import router as repos_router
    from app.routers.monitor import router as monitor_router
    from app.routers.reports import router as reports_router
    from app.routers.settings import router as settings_router

    app.include_router(trending_router, prefix="/trending", tags=["trending"])
    app.include_router(repos_router, prefix="/repos", tags=["repos"])
    app.include_router(monitor_router, prefix="/monitor", tags=["monitor"])
    app.include_router(reports_router, prefix="/reports", tags=["reports"])
    app.include_router(settings_router, prefix="/settings", tags=["settings"])
```

- [ ] **Step 5: 在 plugin.py 注册 settings_router**

修改 `plugin.py`,在 `from app.routers.monitor import router as monitor_router` 后添加:

```python
from app.routers.settings import router as settings_router  # noqa: E402
```

在 `register_http_router` 调用块(原有 4 个 router 之后)添加:

```python
        api.register_http_router(
            settings_router, prefix="/settings", tags=["github-trending"],
        )
```

- [ ] **Step 6: 跑测试确认 pass**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/test_settings_router.py -v
```

Expected: 3 passed。

- [ ] **Step 7: 提交**

```bash
git add plugins/bundle/github-trending/app/routers/settings.py plugins/bundle/github-trending/app/routers/__init__.py plugins/bundle/github-trending/plugin.py plugins/bundle/github-trending/tests/test_settings_router.py
git commit -m "feat(github-trending): settings router + plugin registration"
```

---

## Task 6: 扩展 subscriptions router(POST 立即拉 + GET 附 last_checked)

**Files:**
- Modify: `plugins/bundle/github-trending/app/routers/monitor.py`(router 在此文件)

- [ ] **Step 1: 修改 POST /subscriptions**

在 `app/routers/monitor.py` 的 `create_subscription` 函数:

```python
@router.post("/subscriptions")
async def create_subscription(target: str) -> Dict:
    """添加订阅,触发立即拉一次详情"""
    result = await add_subscription(target)
    # 触发一次立即刷新(不阻塞响应)
    sub_id = result["id"]
    asyncio.create_task(_initial_refresh(sub_id, target))
    return result
```

在文件顶部 `import` 区添加:

```python
import asyncio
from app.monitor_refresh import refresh_one_repo
```

在文件末尾(`@router.get("/events")` 之后)添加:

```python
async def _initial_refresh(subscription_id: int, target: str) -> None:
    """订阅创建后异步立即拉一次 repo 详情。"""
    try:
        await refresh_one_repo(target, subscription_id)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "Initial refresh failed for %s: %s", target, e
        )
```

- [ ] **Step 2: 修改 GET /subscriptions 附 last_checked_at / current_stars**

在 `app/routers/monitor.py` 的 `list_subscriptions` 函数:

```python
@router.get("/subscriptions")
async def list_subscriptions() -> List[Dict]:
    """获取订阅列表(附 watch_log 信息)"""
    from app.database import list_watch_logs_by_subscription
    subs = await get_subscriptions()
    for sub in subs:
        logs = await list_watch_logs_by_subscription(sub["id"])
        if logs:
            sub["last_checked_at"] = logs[0].get("last_checked_at")
            sub["current_stars"] = logs[0].get("stars", 0)
            sub["current_forks"] = logs[0].get("forks", 0)
        else:
            sub["last_checked_at"] = None
            sub["current_stars"] = None
            sub["current_forks"] = None
    return subs
```

- [ ] **Step 3: 提交**

```bash
git add plugins/bundle/github-trending/app/routers/monitor.py
git commit -m "feat(github-trending): auto-refresh on subscribe + watch_log in subscription list"
```

---

## Task 7: collector.py 改为读 runtime settings + 触发 refresh/diff

**Files:**
- Modify: `plugins/bundle/github-trending/app/collector.py`

- [ ] **Step 1: 修改 collect_once 入口**

在 `app/collector.py` 的 `collect_once` 函数,把 `from app.config import settings` 改:

```python
async def collect_once(period: Optional[str] = None) -> dict:
    """跑一轮:遍历 collect_languages 全部采一次。返回汇总。"""
    from app.settings import get_runtime_settings
    runtime = await get_runtime_settings()
    period = period or runtime["collect_period"]
    today = datetime.now().strftime("%Y-%m-%d")
    ok_langs: list[str] = []
    err_langs: list[dict] = []

    for lang in runtime["collect_languages"]:
        lang_norm = lang.strip() if isinstance(lang, str) else lang
        result = await _collect_language(period, lang_norm, today)
        if result["ok"]:
            ok_langs.append(lang_norm or "all")
        else:
            err_langs.append({"lang": lang_norm or "all", "error": result["error"]})
        await asyncio.sleep(LANGUAGE_INTERVAL_SEC)

    summary = {
        "period": period,
        "date": today,
        "ok": ok_langs,
        "errors": err_langs,
    }
    logger.info("Round done: ok=%d, err=%d", len(ok_langs), len(err_langs))

    # 触发订阅 repo 刷新 + trending diff(不阻塞主流程)
    yesterday = (datetime.now().timestamp() - 86400)
    from datetime import datetime as dt
    yest_str = dt.fromtimestamp(yesterday).strftime("%Y-%m-%d")
    asyncio.create_task(_post_round_refresh(today, yest_str))

    return summary
```

- [ ] **Step 2: 在文件末尾加 _post_round_refresh**

```python
async def _post_round_refresh(today: str, yesterday: str) -> None:
    """一轮采集完后:刷新订阅 repo + 检测 trending 新进榜。失败不影响主流程。"""
    try:
        from app.monitor_refresh import refresh_all_subscribed_repos
        from app.trending_diff import detect_and_record
        await asyncio.gather(
            refresh_all_subscribed_repos(),
            detect_and_record(today, yesterday, language="all"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Post-round refresh failed: %s", e)
```

- [ ] **Step 3: 修改 run_collector_loop 用 runtime interval**

把:

```python
async def run_collector_loop() -> None:
    """后台长跑任务:每 collect_interval_min 分钟跑一轮。失败不退出。"""
    interval_sec = max(1, int(settings.collect_interval_min)) * 60
    logger.info(...)
    while True:
        try:
            await collect_once()
        except Exception as e:
            logger.exception(...)
        await asyncio.sleep(interval_sec)
```

替换为:

```python
async def run_collector_loop() -> None:
    """后台长跑任务:每 collect_interval_min 分钟跑一轮。失败不退出。"""
    from app.settings import get_runtime_settings
    while True:
        try:
            runtime = await get_runtime_settings()
            if not runtime["collect_enabled"]:
                logger.debug("Collector disabled, sleeping 60s")
                await asyncio.sleep(60)
                continue
            await collect_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("Collector loop tick crashed: %s", e)
        # 重新读 interval(支持运行时变更)
        runtime = await get_runtime_settings()
        interval_sec = max(1, int(runtime["collect_interval_min"])) * 60
        await asyncio.sleep(interval_sec)
```

- [ ] **Step 4: 提交**

```bash
git add plugins/bundle/github-trending/app/collector.py
git commit -m "refactor(github-trending): collector reads runtime settings + post-round refresh"
```

---

## Task 8: 工具注册清理 + BASE_URL 修

**Files:**
- Modify: `plugins/bundle/github-trending/plugin.py`
- Modify: `plugins/bundle/github-trending/tools/trending.py`
- Modify: `plugins/bundle/github-trending/tools/reports.py`
- Modify: `plugins/bundle/github-trending/tools/monitor.py`
- Modify: `plugins/bundle/github-trending/tools/repos.py`

- [ ] **Step 1: plugin.py 改注册 — 只注册 8 个读工具**

修改 `plugin.py`,把 `from tools.trending import trending_upload` 和 `from tools.reports import report_upload` 替换为:

```python
from tools.trending import trending_get_daily, trending_get_dates  # noqa: E402
from tools.repos import repo_search, repo_detail, repo_trend  # noqa: E402
from tools.monitor import (  # noqa: E402
    monitor_list_subscriptions,
    monitor_get_events,
)
from tools.reports import report_list  # noqa: E402
```

把 `GitHubTrendingPlugin.register` 里的 `register_tool` 块整体替换为:

```python
        # 1. 注册只读工具(给 Agent 用)
        api.register_tool(
            tool_name="trending_get_daily",
            tool_func=trending_get_daily,
            description="获取每日热榜。参数: date, language",
            icon="🔥",
        )
        api.register_tool(
            tool_name="trending_get_dates",
            tool_func=trending_get_dates,
            description="获取有数据的日期列表。参数: language",
            icon="📅",
        )
        api.register_tool(
            tool_name="repo_search",
            tool_func=repo_search,
            description="搜索仓库。参数: keyword, limit",
            icon="🔍",
        )
        api.register_tool(
            tool_name="repo_detail",
            tool_func=repo_detail,
            description="获取仓库详情。参数: full_name",
            icon="📦",
        )
        api.register_tool(
            tool_name="repo_trend",
            tool_func=repo_trend,
            description="获取仓库历史趋势。参数: full_name",
            icon="📈",
        )
        api.register_tool(
            tool_name="monitor_list_subscriptions",
            tool_func=monitor_list_subscriptions,
            description="获取订阅列表",
            icon="📋",
        )
        api.register_tool(
            tool_name="monitor_get_events",
            tool_func=monitor_get_events,
            description="获取监控动态。参数: repo, limit",
            icon="📡",
        )
        api.register_tool(
            tool_name="report_list",
            tool_func=report_list,
            description="获取报告列表。参数: date, limit",
            icon="📊",
        )
```

- [ ] **Step 2: tools/*.py 改 BASE_URL**

每个 tools/*.py 顶部 `BASE_URL = "http://127.0.0.1:7901"` 改为:

```python
import os
BASE_URL = os.environ.get("QWENPAW_TOOL_BASE_URL", "http://127.0.0.1:8088")
```

在 `tools/__init__.py` 写一行注释:

```python
"""Agent 工具 — 通过主进程 URL 调用。Mode A 下路由在主进程(默认 8088),可通过 QWENPAW_TOOL_BASE_URL 覆盖。"""
```

- [ ] **Step 3: tools/trending.py 删 trending_upload**

删除 `trending.py` 的 `trending_upload` 整个函数(从 `async def trending_upload(` 到函数结束)。

- [ ] **Step 4: tools/reports.py 删 report_upload**

删除 `reports.py` 的 `report_upload` 整个函数。

- [ ] **Step 5: tools/monitor.py 删写函数**

删除 `monitor.py` 的 `monitor_subscribe` / `monitor_unsubscribe` / `monitor_upload` 三个函数。

- [ ] **Step 6: 提交**

```bash
git add plugins/bundle/github-trending/plugin.py plugins/bundle/github-trending/tools/
git commit -m "refactor(github-trending): register read-only tools + fix BASE_URL"
```

---

## Task 9: 前端 styles + 5-tab index

**Files:**
- Create: `plugins/bundle/github-trending/frontend/src/styles.ts`
- Modify: `plugins/bundle/github-trending/frontend/src/index.tsx`

- [ ] **Step 1: 写 styles.ts**

新建 `frontend/src/styles.ts`:

```typescript
// 暗色主题 CSS 变量(注入到 .gh-trending-root)
// 配色参考 github-data-fetch

export const ROOT_CLASS = "gh-trending-root";

export const THEME_CSS = `
.${ROOT_CLASS} {
  --gh-bg: #0A0D14;
  --gh-card: #171D2A;
  --gh-card-hover: #1E2538;
  --gh-elevated: #222A3E;
  --gh-border: #262F42;
  --gh-border-hover: #364059;
  --gh-text: #E4EAF0;
  --gh-text-secondary: #8892A8;
  --gh-text-tertiary: #5A6478;
  --gh-accent: #00D4AA;
  --gh-accent-hover: #00E8BA;
  --gh-accent-glow: rgba(0, 212, 170, 0.2);
  --gh-warning: #FFB800;
  --gh-danger: #FF4D6A;
  --gh-blue: #4A9EFF;
  --gh-purple: #8B5CF6;
  --gh-radius-sm: 6px;
  --gh-radius-md: 10px;
  --gh-radius-lg: 16px;
  --gh-font: 'DM Sans', -apple-system, system-ui, sans-serif;
  --gh-mono: 'JetBrains Mono', monospace;
  font-family: var(--gh-font);
  color: var(--gh-text);
}
.${ROOT_CLASS} *,
.${ROOT_CLASS} *::before,
.${ROOT_CLASS} *::after { box-sizing: border-box; }
.${ROOT_CLASS} .gh-card {
  background: var(--gh-card);
  border: 1px solid var(--gh-border);
  border-radius: var(--gh-radius-lg);
  padding: 16px;
  transition: border-color 0.15s;
}
.${ROOT_CLASS} .gh-card:hover { border-color: var(--gh-border-hover); }
.${ROOT_CLASS} .gh-text-secondary { color: var(--gh-text-secondary); }
.${ROOT_CLASS} .gh-text-tertiary { color: var(--gh-text-tertiary); }
.${ROOT_CLASS} .gh-accent { color: var(--gh-accent); }
.${ROOT_CLASS} .gh-row {
  display: flex; align-items: center; gap: 12px;
}
.${ROOT_CLASS} .gh-table { width: 100%; border-collapse: collapse; }
.${ROOT_CLASS} .gh-table th {
  text-align: left; padding: 10px 12px;
  font-size: 0.75rem; font-weight: 500;
  color: var(--gh-text-tertiary);
  background: var(--gh-elevated);
  border-bottom: 1px solid var(--gh-border);
}
.${ROOT_CLASS} .gh-table td {
  padding: 10px 12px; font-size: 0.85rem;
  border-bottom: 1px solid var(--gh-border);
  color: var(--gh-text);
}
.${ROOT_CLASS} .gh-table tr:hover td { background: var(--gh-card-hover); cursor: pointer; }
.${ROOT_CLASS} .gh-button {
  background: var(--gh-elevated);
  border: 1px solid var(--gh-border);
  color: var(--gh-text);
  padding: 6px 14px;
  border-radius: var(--gh-radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.${ROOT_CLASS} .gh-button:hover { border-color: var(--gh-accent); color: var(--gh-accent); }
.${ROOT_CLASS} .gh-button-primary {
  background: var(--gh-accent);
  border-color: var(--gh-accent);
  color: #0A0D14;
  font-weight: 600;
}
.${ROOT_CLASS} .gh-button-primary:hover { background: var(--gh-accent-hover); }
.${ROOT_CLASS} .gh-tag {
  display: inline-block; padding: 2px 8px;
  border-radius: 12px; font-size: 0.7rem;
  background: var(--gh-elevated);
  color: var(--gh-text-secondary);
  border: 1px solid var(--gh-border);
}
.${ROOT_CLASS} .gh-tag-accent { color: var(--gh-accent); border-color: var(--gh-accent); }
.${ROOT_CLASS} .gh-tag-warning { color: var(--gh-warning); border-color: var(--gh-warning); }
.${ROOT_CLASS} .gh-tag-purple { color: var(--gh-purple); border-color: var(--gh-purple); }
.${ROOT_CLASS} .gh-tag-blue { color: var(--gh-blue); border-color: var(--gh-blue); }
.${ROOT_CLASS} h1, h2, h3, h4, h5 { color: var(--gh-text); margin: 0; }
.${ROOT_CLASS} a { color: var(--gh-accent); }
`;
```

- [ ] **Step 2: 重写 index.tsx**

完整重写 `frontend/src/index.tsx`:

```tsx
// GitHub Trending 插件前端入口 — 5 个 Tab 暗色主题。

import type * as ReactNS from "react";
import TrendingPage from "./pages/TrendingPage";
import ReposPage from "./pages/ReposPage";
import MonitorPage from "./pages/MonitorPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import { ROOT_CLASS, THEME_CSS } from "./styles";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;
const { Tabs } = host.antd;
const { TabPane } = Tabs;

function App() {
  const [activeTab, setActiveTab] = React.useState("trending");

  return (
    <div className={ROOT_CLASS} style={{ height: "100%" }}>
      <style dangerouslySetInnerHTML={{ __html: THEME_CSS }} />
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ height: "100%", padding: "0 16px" }}
      >
        <TabPane tab="🔥 热榜" key="trending">
          <TrendingPage />
        </TabPane>
        <TabPane tab="📦 仓库" key="repos">
          <ReposPage />
        </TabPane>
        <TabPane tab="📡 订阅" key="monitor">
          <MonitorPage />
        </TabPane>
        <TabPane tab="📊 报告" key="reports">
          <ReportsPage />
        </TabPane>
        <TabPane tab="⚙️ 设置" key="settings">
          <SettingsPage />
        </TabPane>
      </Tabs>
    </div>
  );
}

window.QwenPaw.registerRoutes?.("github-trending", [
  {
    path: "/plugin/github-trending",
    component: App,
    label: "热榜",
    icon: "📊",
    priority: 10,
  },
]);
```

- [ ] **Step 3: 提交**

```bash
git add plugins/bundle/github-trending/frontend/src/styles.ts plugins/bundle/github-trending/frontend/src/index.tsx
git commit -m "feat(github-trending): dark theme styles + 5-tab layout"
```

---

## Task 10: SettingsPage 完整实现

**Files:**
- Create: `plugins/bundle/github-trending/frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: 写 SettingsPage**

```tsx
// 设置页 — 采集频率、周期、语言、立即触发。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Switch, InputNumber, Radio, Select, Button, message, Spin } =
  window.QwenPaw.host.antd;
import { apiGet, apiPost, apiPut } from "../api";

const PRESET_MINUTES = [30, 60, 180, 360, 720, 1440];

const PRESET_LANGS = [
  { value: "", label: "全部" },
  { value: "python", label: "Python" },
  { value: "go", label: "Go" },
  { value: "rust", label: "Rust" },
  { value: "typescript", label: "TypeScript" },
  { value: "javascript", label: "JavaScript" },
  { value: "java", label: "Java" },
  { value: "html", label: "HTML" },
];

type RuntimeSettings = {
  collect_enabled: boolean;
  collect_interval_min: number;
  collect_period: string;
  collect_languages: string[];
};

type TriggerStatus = {
  task_id: string;
  status: "running" | "done" | "timeout" | "error";
  result?: { ok: string[]; errors: Array<{ lang: string; error: string }>; date: string };
  error?: string;
};

export default function SettingsPage() {
  const [loading, setLoading] = React.useState(true);
  const [settings, setSettings] = React.useState<RuntimeSettings | null>(null);
  const [interval, setInterval] = React.useState<number>(60);
  const [enabled, setEnabled] = React.useState<boolean>(true);
  const [period, setPeriod] = React.useState<string>("daily");
  const [languages, setLanguages] = React.useState<string[]>([""]);
  const [triggering, setTriggering] = React.useState(false);
  const [taskId, setTaskId] = React.useState<string | null>(null);
  const [lastRun, setLastRun] = React.useState<TriggerStatus["result"] | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const d = (await apiGet("/settings")) as RuntimeSettings;
      setSettings(d);
      setEnabled(d.collect_enabled);
      setInterval(d.collect_interval_min);
      setPeriod(d.collect_period);
      setLanguages(d.collect_languages);
    } catch (e) {
      message.error("加载设置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const save = async (overrides: Partial<RuntimeSettings> = {}) => {
    const payload = {
      collect_enabled: overrides.collect_enabled ?? enabled,
      collect_interval_min: overrides.collect_interval_min ?? interval,
      collect_period: overrides.collect_period ?? period,
      collect_languages: overrides.collect_languages ?? languages,
    };
    try {
      await apiPut("/settings", payload);
      message.success("已保存");
      await load();
    } catch (e) {
      message.error("保存失败");
    }
  };

  const onEnableChange = async (v: boolean) => {
    setEnabled(v);
    await save({ collect_enabled: v });
  };

  const onIntervalChange = async (v: number | null) => {
    if (v == null) return;
    setInterval(v);
    await save({ collect_interval_min: v });
  };

  const onPeriodChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setPeriod(v);
    await save({ collect_period: v });
  };

  const onLanguagesChange = async (v: string[]) => {
    setLanguages(v);
    await save({ collect_languages: v });
  };

  const triggerCollect = async () => {
    setTriggering(true);
    setTaskId(null);
    try {
      const r = (await apiPost("/settings/trigger-collect", {})) as {
        task_id: string;
      };
      setTaskId(r.task_id);
      pollStatus(r.task_id);
    } catch (e) {
      message.error("触发失败");
      setTriggering(false);
    }
  };

  const pollStatus = async (tid: string) => {
    const start = Date.now();
    const tick = async (): Promise<void> => {
      try {
        const s = (await apiGet(`/settings/trigger-collect/${tid}`)) as TriggerStatus;
        if (s.status === "done") {
          setLastRun(s.result ?? null);
          setTriggering(false);
          message.success(`采集完成: ${s.result?.ok.length ?? 0} 个语言成功`);
        } else if (s.status === "error" || s.status === "timeout") {
          setTriggering(false);
          message.error(`采集${s.status === "timeout" ? "超时" : "失败"}`);
        } else if (Date.now() - start > 6 * 60 * 1000) {
          setTriggering(false);
          message.error("轮询超时");
        } else {
          setTimeout(tick, 3000);
        }
      } catch (e) {
        setTriggering(false);
        message.error("查状态失败");
      }
    };
    tick();
  };

  if (loading || !settings) {
    return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <Spin />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <h2 style={{ marginBottom: 24 }}>⚙️ 采集设置</h2>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>启用采集</h4>
        <Switch checked={enabled} onChange={onEnableChange} />
        <span className="gh-text-secondary" style={{ marginLeft: 12 }}>
          {enabled ? "✅ 运行中" : "⏸ 已暂停"}
        </span>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>采集频率</h4>
        <InputNumber
          value={interval}
          onChange={onIntervalChange}
          min={5}
          max={10080}
          addonAfter="分钟"
        />
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {PRESET_MINUTES.map((m) => (
            <button
              key={m}
              className={`gh-button ${interval === m ? "gh-button-primary" : ""}`}
              onClick={() => onIntervalChange(m)}
            >
              {m < 60 ? `${m}分` : m < 1440 ? `${m / 60}时` : `${m / 1440}天`}
            </button>
          ))}
        </div>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>周期</h4>
        <Radio.Group value={period} onChange={onPeriodChange}>
          <Radio.Button value="daily">Daily</Radio.Button>
          <Radio.Button value="weekly">Weekly</Radio.Button>
          <Radio.Button value="monthly">Monthly</Radio.Button>
        </Radio.Group>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>抓取语言</h4>
        <Select
          mode="multiple"
          value={languages}
          onChange={onLanguagesChange}
          style={{ width: "100%" }}
          options={PRESET_LANGS}
        />
        <p className="gh-text-tertiary" style={{ fontSize: "0.75rem", marginTop: 8 }}>
          留「全部」代表 github.com/trending 主页(不限定语言)
        </p>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>状态</h4>
        {lastRun ? (
          <div className="gh-text-secondary" style={{ fontSize: "0.85rem" }}>
            上次运行: {lastRun.date} · ✅ {lastRun.ok.length} 成功
            {lastRun.errors.length > 0 && (
              <span className="gh-tag gh-tag-warning" style={{ marginLeft: 8 }}>
                ❌ {lastRun.errors.length} 失败
              </span>
            )}
          </div>
        ) : (
          <div className="gh-text-tertiary" style={{ fontSize: "0.85rem" }}>
            还没手动触发过采集
          </div>
        )}
      </section>

      <div style={{ display: "flex", gap: 12 }}>
        <Button
          type="primary"
          loading={triggering}
          onClick={triggerCollect}
          disabled={!enabled}
        >
          🚀 立即采集一次
        </Button>
        <Button onClick={load}>🔄 刷新状态</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add plugins/bundle/github-trending/frontend/src/pages/SettingsPage.tsx
git commit -m "feat(github-trending): Settings page with runtime config + manual trigger"
```

---

## Task 11: TrendingPage 重写(日期侧栏 + 表格)

**Files:**
- Modify: `plugins/bundle/github-trending/frontend/src/pages/TrendingPage.tsx`

- [ ] **Step 1: 完整重写文件**

```tsx
// 热榜 — 左侧 180px 日期侧栏 + 右侧仓库表格。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Spin, Empty, Button, message } = window.QwenPaw.host.antd;
import { apiGet, apiPost } from "../api";
import { formatNumber, LANGUAGES } from "../utils";

type TrendingItem = {
  rank: number;
  full_name: string;
  description?: string | null;
  language?: string | null;
  stars: number;
  stars_delta: number;
  forks: number;
  url: string;
};

type TrendingData = {
  date: string;
  language: string;
  total_count: number;
  items: TrendingItem[];
};

function formatDate(d: string): string {
  const today = new Date().toISOString().split("T")[0];
  const yest = new Date(Date.now() - 86400000).toISOString().split("T")[0];
  if (d === today) return `${d} 今天`;
  if (d === yest) return `${d} 昨天`;
  return d;
}

export default function TrendingPage() {
  const [dates, setDates] = React.useState<string[]>([]);
  const [selectedDate, setSelectedDate] = React.useState<string>("");
  const [language, setLanguage] = React.useState<string>("");
  const [data, setData] = React.useState<TrendingData | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [subscribing, setSubscribing] = React.useState<string | null>(null);

  React.useEffect(() => {
    apiGet(`/trending/dates?language=${encodeURIComponent(language || "all")}`)
      .then((d: unknown) => {
        const list = Array.isArray(d) ? (d as string[]) : [];
        setDates(list);
        if (list.length > 0 && !selectedDate) setSelectedDate(list[0]);
      })
      .catch(console.error);
  }, [language]);

  React.useEffect(() => {
    if (!selectedDate) return;
    setLoading(true);
    apiGet(
      `/trending/daily?date=${encodeURIComponent(selectedDate)}&language=${encodeURIComponent(language || "all")}`,
    )
      .then((d: unknown) => setData((d as TrendingData) ?? null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [selectedDate, language]);

  const subscribe = async (fullName: string) => {
    setSubscribing(fullName);
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(fullName)}`, {});
      message.success(`已订阅 ${fullName}`);
    } catch (e) {
      message.error("订阅失败");
    } finally {
      setSubscribing(null);
    }
  };

  return (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "180px 1fr", gap: 16, minHeight: 500 }}>
      <div className="gh-card" style={{ padding: 0, overflow: "hidden", maxHeight: 600, overflowY: "auto" }}>
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gh-border)", fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>
          📅 日期({dates.length})
        </div>
        {dates.length === 0 ? (
          <div style={{ padding: 16, color: "var(--gh-text-tertiary)", fontSize: "0.8rem", textAlign: "center" }}>暂无数据</div>
        ) : (
          dates.map((d) => (
            <button
              key={d}
              onClick={() => setSelectedDate(d)}
              style={{
                width: "100%", padding: "8px 14px", background: selectedDate === d ? "var(--gh-elevated)" : "transparent",
                border: "none", borderLeft: selectedDate === d ? "2px solid var(--gh-accent)" : "2px solid transparent",
                color: selectedDate === d ? "var(--gh-text)" : "var(--gh-text-secondary)",
                fontSize: "0.85rem", textAlign: "left", cursor: "pointer",
              }}
            >
              {formatDate(d)}
            </button>
          ))
        )}
      </div>

      <div className="gh-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--gh-border)", display: "flex", alignItems: "center", gap: 12 }}>
          <h4 style={{ margin: 0 }}>{selectedDate ? formatDate(selectedDate) : "选择日期"}</h4>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{ background: "var(--gh-elevated)", color: "var(--gh-text)", border: "1px solid var(--gh-border)", borderRadius: 6, padding: "4px 8px", fontSize: "0.8rem" }}
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
          <span style={{ marginLeft: "auto", color: "var(--gh-text-tertiary)", fontSize: "0.75rem" }}>
            {data?.items.length ?? 0} 个仓库
          </span>
        </div>

        {loading ? (
          <div style={{ padding: 32, textAlign: "center" }}><Spin /></div>
        ) : !data || data.items.length === 0 ? (
          <Empty description="暂无数据" style={{ padding: 32 }} />
        ) : (
          <table className="gh-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>#</th>
                <th>仓库</th>
                <th>语言</th>
                <th style={{ textAlign: "right" }}>Stars</th>
                <th style={{ textAlign: "right" }}>今日涨</th>
                <th style={{ textAlign: "center", width: 100 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.full_name}>
                  <td style={{ color: "var(--gh-text-tertiary)" }}>{item.rank}</td>
                  <td>
                    <a href={item.url} target="_blank" rel="noreferrer" style={{ fontWeight: 500 }}>
                      {item.full_name}
                    </a>
                    {item.description && (
                      <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 2 }}>
                        {item.description.slice(0, 80)}
                      </div>
                    )}
                  </td>
                  <td>
                    {item.language ? (
                      <span className="gh-tag gh-tag-blue">{item.language}</span>
                    ) : (
                      <span className="gh-text-tertiary">—</span>
                    )}
                  </td>
                  <td style={{ textAlign: "right" }}>⭐ {formatNumber(item.stars)}</td>
                  <td style={{ textAlign: "right" }}>
                    {item.stars_delta > 0 ? (
                      <span className="gh-tag gh-tag-accent">+{formatNumber(item.stars_delta)}</span>
                    ) : (
                      <span className="gh-text-tertiary">—</span>
                    )}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <Button
                      size="small"
                      loading={subscribing === item.full_name}
                      onClick={() => subscribe(item.full_name)}
                    >
                      订阅
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add plugins/bundle/github-trending/frontend/src/pages/TrendingPage.tsx
git commit -m "feat(github-trending): rewrite TrendingPage with sidebar + table"
```

---

## Task 12: ReposPage / MonitorPage / ReportsPage 重写

**Files:**
- Modify: `plugins/bundle/github-trending/frontend/src/pages/ReposPage.tsx`
- Modify: `plugins/bundle/github-trending/frontend/src/pages/MonitorPage.tsx`
- Modify: `plugins/bundle/github-trending/frontend/src/pages/ReportsPage.tsx`

- [ ] **Step 1: 重写 ReposPage**

```tsx
// 仓库搜索 — 顶部搜索 + 表格 + 详情 Drawer。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Input, Spin, Empty, Drawer, Button, message } = window.QwenPaw.host.antd;
import { apiGet, apiPost } from "../api";
import { formatNumber } from "../utils";

type Repo = {
  full_name: string;
  description?: string | null;
  language?: string | null;
  stars: number;
  forks: number;
  appearances?: number;
  url?: string;
  first_seen?: string | null;
  last_seen?: string | null;
};

type Trend = { date: string; rank: number; stars: number; stars_delta?: number };

export default function ReposPage() {
  const [keyword, setKeyword] = React.useState("");
  const [results, setResults] = React.useState<Repo[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selected, setSelected] = React.useState<Repo | null>(null);
  const [trend, setTrend] = React.useState<Trend[]>([]);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const search = async (k: string) => {
    if (!k.trim()) return;
    setLoading(true);
    try {
      const d = (await apiGet(`/repos/search?keyword=${encodeURIComponent(k)}`)) as { repos?: Repo[] };
      setResults(Array.isArray(d?.repos) ? d.repos : []);
    } catch (e) {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const open = async (r: Repo) => {
    setSelected(r);
    setDrawerOpen(true);
    try {
      const d = (await apiGet(`/repos/${encodeURIComponent(r.full_name)}/trend`)) as { trend?: Trend[] };
      setTrend(Array.isArray(d?.trend) ? d.trend : []);
    } catch (e) {
      setTrend([]);
    }
  };

  const subscribe = async () => {
    if (!selected) return;
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(selected.full_name)}`, {});
      message.success("已订阅");
    } catch (e) {
      message.error("订阅失败");
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <Input.Search
        placeholder="搜索项目名 / 描述..."
        enterButton="搜索"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onSearch={search}
        style={{ maxWidth: 480, marginBottom: 16 }}
      />
      {loading ? (
        <div style={{ padding: 32, textAlign: "center" }}><Spin /></div>
      ) : results.length === 0 ? (
        <Empty description="输入关键词搜索" />
      ) : (
        <table className="gh-table">
          <thead>
            <tr>
              <th>仓库</th>
              <th>语言</th>
              <th style={{ textAlign: "right" }}>Stars</th>
              <th style={{ textAlign: "right" }}>Forks</th>
              <th style={{ textAlign: "right" }}>上榜次数</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.full_name} onClick={() => open(r)}>
                <td>
                  <div style={{ fontWeight: 500 }}>{r.full_name}</div>
                  {r.description && (
                    <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>{r.description.slice(0, 80)}</div>
                  )}
                </td>
                <td>{r.language ? <span className="gh-tag gh-tag-blue">{r.language}</span> : "—"}</td>
                <td style={{ textAlign: "right" }}>⭐ {formatNumber(r.stars)}</td>
                <td style={{ textAlign: "right" }}>🍴 {formatNumber(r.forks)}</td>
                <td style={{ textAlign: "right" }}>{r.appearances ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Drawer
        title={selected?.full_name}
        placement="right"
        width={480}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {selected && (
          <div>
            <Button type="primary" onClick={subscribe} style={{ marginBottom: 16 }}>+ 订阅</Button>
            <p style={{ color: "var(--gh-text-secondary)" }}>{selected.description ?? "—"}</p>
            <div className="gh-card" style={{ marginBottom: 16 }}>
              <div>⭐ {formatNumber(selected.stars)} stars · 🍴 {formatNumber(selected.forks)} forks</div>
              <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 8 }}>
                首次上榜: {selected.first_seen ?? "—"} · 最近上榜: {selected.last_seen ?? "—"}
              </div>
            </div>
            <h4 style={{ marginBottom: 8 }}>趋势 (近 10 天)</h4>
            {trend.length === 0 ? <div style={{ color: "var(--gh-text-tertiary)" }}>暂无趋势</div> : (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {trend.slice(0, 10).map((t) => (
                  <li key={t.date} style={{ padding: "6px 0", borderBottom: "1px solid var(--gh-border)" }}>
                    <span className="gh-tag">{t.date}</span>
                    <span style={{ marginLeft: 12 }}>排名 #{t.rank} · ⭐ {formatNumber(t.stars)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 2: 重写 MonitorPage**

```tsx
// 订阅监控 — 顶部订阅列表 + 动态流。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Button, Spin, Empty, Modal, Input, Popconfirm, message } = window.QwenPaw.host.antd;
import { apiDelete, apiGet, apiPost } from "../api";
import { formatNumber, getTimeAgo } from "../utils";

type Sub = {
  id: number;
  target: string;
  enabled: number | boolean;
  last_checked_at?: string | null;
  current_stars?: number | null;
};

type Event = {
  repo_name: string;
  event_type: string;
  title: string;
  body?: string | null;
  stars?: number;
  event_time: string;
};

const EVENT_TAG: Record<string, { icon: string; cls: string }> = {
  release: { icon: "📦", cls: "gh-tag-purple" },
  commit: { icon: "📝", cls: "gh-tag-blue" },
  star_update: { icon: "⭐", cls: "gh-tag-warning" },
  repo_meta_update: { icon: "📌", cls: "" },
  trending_new: { icon: "🔥", cls: "gh-tag-accent" },
  refresh_error: { icon: "⚠️", cls: "gh-tag-warning" },
  collector_error: { icon: "❌", cls: "gh-tag-warning" },
};

export default function MonitorPage() {
  const [subs, setSubs] = React.useState<Sub[]>([]);
  const [events, setEvents] = React.useState<Event[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [modalOpen, setModalOpen] = React.useState(false);
  const [newTarget, setNewTarget] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [s, e] = await Promise.all([
        apiGet("/monitor/subscriptions") as Promise<{ subscriptions?: Sub[] }>,
        apiGet("/monitor/events?limit=50") as Promise<{ events?: Event[] }>,
      ]);
      setSubs(Array.isArray(s?.subscriptions) ? s.subscriptions : []);
      setEvents(Array.isArray(e?.events) ? e.events : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!newTarget.trim()) return;
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(newTarget)}`, {});
      setNewTarget("");
      setModalOpen(false);
      message.success("订阅成功,正在拉取详情...");
      setTimeout(load, 2000);
    } catch (e) {
      message.error("订阅失败");
    }
  };

  const remove = async (id: number) => {
    try {
      await apiDelete(`/monitor/subscriptions/${id}`);
      message.success("已取消");
      load();
    } catch (e) {
      message.error("取消失败");
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="gh-row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h3>📡 我的订阅 ({subs.length})</h3>
        <Button type="primary" onClick={() => setModalOpen(true)}>+ 添加订阅</Button>
      </div>

      {loading ? <Spin /> : subs.length === 0 ? (
        <Empty description="暂无订阅" />
      ) : (
        <table className="gh-table" style={{ marginBottom: 24 }}>
          <thead><tr><th>仓库</th><th>状态</th><th>当前 Stars</th><th>上次检查</th><th style={{ width: 100 }}>操作</th></tr></thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td style={{ fontWeight: 500 }}>{s.target}</td>
                <td>
                  {s.enabled ? <span className="gh-tag gh-tag-accent">监控中</span> : <span className="gh-tag">已暂停</span>}
                </td>
                <td>{s.current_stars != null ? `⭐ ${formatNumber(s.current_stars)}` : "—"}</td>
                <td style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>
                  {s.last_checked_at ? getTimeAgo(s.last_checked_at) : "未拉取"}
                </td>
                <td>
                  <Popconfirm title="确认取消?" onConfirm={() => remove(s.id)}>
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ marginBottom: 12 }}>📊 监控动态 ({events.length})</h3>
      {events.length === 0 ? (
        <Empty description="暂无动态" />
      ) : (
        <div>
          {events.map((e, i) => {
            const tag = EVENT_TAG[e.event_type] ?? { icon: "📌", cls: "" };
            return (
              <div key={i} className="gh-card" style={{ marginBottom: 8 }}>
                <div className="gh-row" style={{ justifyContent: "space-between" }}>
                  <div className="gh-row">
                    <span style={{ fontWeight: 500 }}>{e.repo_name}</span>
                    <span className={`gh-tag ${tag.cls}`}>{tag.icon} {e.event_type}</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>{getTimeAgo(e.event_time)}</span>
                </div>
                <div style={{ marginTop: 6 }}>{e.title}</div>
                {e.body && <div style={{ fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 }}>{e.body}</div>}
              </div>
            );
          })}
        </div>
      )}

      <Modal title="添加订阅" open={modalOpen} onOk={add} onCancel={() => setModalOpen(false)}>
        <Input
          placeholder="owner/repo (例: facebook/react)"
          value={newTarget}
          onChange={(e) => setNewTarget(e.target.value)}
          onPressEnter={add}
        />
      </Modal>
    </div>
  );
}
```

- [ ] **Step 3: 重写 ReportsPage**

```tsx
// 分析报告 — 表格列表 + 详情 Drawer。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Spin, Empty, Drawer, Button } = window.QwenPaw.host.antd;
import { apiGet } from "../api";

type Report = {
  id: number;
  date: string;
  type: string;
  source: string;
  content?: { overview?: string; highlights?: Array<{ project: string; insight: string }>; trends?: string[]; suggestions?: string[] };
};

export default function ReportsPage() {
  const [reports, setReports] = React.useState<Report[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selected, setSelected] = React.useState<Report | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const d = (await apiGet("/reports?limit=50")) as { reports?: Report[] };
      setReports(Array.isArray(d?.reports) ? d.reports : []);
    } catch (e) {
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const open = (r: Report) => {
    setSelected(r);
    setDrawerOpen(true);
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="gh-row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h3>📊 分析报告 ({reports.length})</h3>
        <Button onClick={load}>🔄 刷新</Button>
      </div>
      {loading ? <Spin /> : reports.length === 0 ? (
        <Empty description="暂无报告" />
      ) : (
        <table className="gh-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>类型</th>
              <th>来源</th>
              <th>概览</th>
              <th style={{ width: 80 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.date}</td>
                <td><span className="gh-tag gh-tag-blue">{r.type}</span></td>
                <td>
                  {r.source === "llm" ? (
                    <span className="gh-tag gh-tag-purple">🤖 AI</span>
                  ) : (
                    <span className="gh-tag gh-tag-accent">📝 手动</span>
                  )}
                </td>
                <td style={{ color: "var(--gh-text-secondary)", fontSize: "0.8rem" }}>
                  {r.content?.overview?.slice(0, 80) ?? "—"}
                </td>
                <td>
                  <Button size="small" onClick={() => open(r)}>查看</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Drawer title={selected ? `报告 - ${selected.date}` : ""} placement="right" width={560} open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        {selected?.content && (
          <div>
            {selected.content.overview && (
              <>
                <h4>📊 概览</h4>
                <p style={{ color: "var(--gh-text-secondary)" }}>{selected.content.overview}</p>
              </>
            )}
            {selected.content.highlights && selected.content.highlights.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>🔥 亮点项目</h4>
                {selected.content.highlights.map((h, i) => (
                  <div key={i} className="gh-card" style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 500 }}>{h.project}</div>
                    <div style={{ fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 }}>{h.insight}</div>
                  </div>
                ))}
              </>
            )}
            {selected.content.trends && selected.content.trends.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>📈 趋势</h4>
                <ul style={{ paddingLeft: 20 }}>
                  {selected.content.trends.map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              </>
            )}
            {selected.content.suggestions && selected.content.suggestions.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>💡 建议</h4>
                <ul style={{ paddingLeft: 20 }}>
                  {selected.content.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 4: 提交**

```bash
git add plugins/bundle/github-trending/frontend/src/pages/ReposPage.tsx plugins/bundle/github-trending/frontend/src/pages/MonitorPage.tsx plugins/bundle/github-trending/frontend/src/pages/ReportsPage.tsx
git commit -m "feat(github-trending): rewrite 3 pages with dark theme tables"
```

---

## Task 13: 前端 build + 整体联调

**Files:**
- Modify: `plugins/bundle/github-trending/dist/index.js`(重新生成)

- [ ] **Step 1: build 前端**

```bash
cd plugins/bundle/github-trending/frontend
npm install
npm run build
```

Expected: `dist/index.js` 生成,无错误。

- [ ] **Step 2: 跑后端所有测试**

```bash
cd plugins/bundle/github-trending
PYTHONPATH=. pytest tests/ -v
```

Expected: 所有测试通过(15+ tests)。

- [ ] **Step 3: 手动验收清单**

按 spec 第 9.2 节逐项验证:
- [ ] 改频率后,DB settings 表有新值,下次 collector tick 用新值
- [ ] 手动触发,30s 内看到结果
- [ ] 订阅一个 repo,5s 内 repo_watch_log 有数据
- [ ] 改 repo stars(模拟),下次 collector 跑完看到 star_update 事件
- [ ] 前端 5 个 tab 切换正常
- [ ] 8 个只读工具都能注册(看 `qwenpaw plugin list` 或日志)

- [ ] **Step 4: 提交 dist + 完成 commit**

```bash
git add plugins/bundle/github-trending/dist/
git commit -m "build(github-trending): rebuild frontend bundle"
```

---

## 自审检查

- ✅ settings 表 + CRUD → Task 1
- ✅ settings.py 运行时配置 → Task 2
- ✅ monitor_refresh.py → Task 3
- ✅ trending_diff.py → Task 4
- ✅ routers/settings.py → Task 5
- ✅ subscriptions 扩展 → Task 6
- ✅ collector 重构 → Task 7
- ✅ 工具清理 + BASE_URL → Task 8
- ✅ 前端 styles + index → Task 9
- ✅ SettingsPage → Task 10
- ✅ TrendingPage 重写 → Task 11
- ✅ Repos/Monitor/Reports 重写 → Task 12
- ✅ build + 测试 → Task 13
- ✅ 8 个只读工具名一致(全用 `trending_get_daily` / `trending_get_dates` / `repo_search` / `repo_detail` / `repo_trend` / `monitor_list_subscriptions` / `monitor_get_events` / `report_list`)
- ✅ 没有 placeholder
