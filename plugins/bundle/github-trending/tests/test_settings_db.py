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


async def test_watch_log_upsert_and_get(fresh_db):
    info = {"stars": 100, "forks": 10, "language": "Python", "description": "A test repo"}
    await database.upsert_watch_log(1, "owner/repo", info)
    log = await database.get_watch_log(1, "owner/repo")
    assert log is not None
    assert log["stars"] == 100
    assert log["forks"] == 10
    assert log["language"] == "Python"
    assert log["description"] == "A test repo"
    assert log["last_checked_at"] is not None


async def test_watch_log_upsert_updates_existing(fresh_db):
    info1 = {"stars": 100, "forks": 10, "language": "Python", "description": "First"}
    info2 = {"stars": 200, "forks": 20, "language": "Python", "description": "Second"}
    await database.upsert_watch_log(1, "owner/repo", info1)
    await database.upsert_watch_log(1, "owner/repo", info2)
    log = await database.get_watch_log(1, "owner/repo")
    assert log["stars"] == 200
    assert log["description"] == "Second"


async def test_watch_log_list_by_subscription(fresh_db):
    await database.upsert_watch_log(1, "owner/a", {"stars": 10, "forks": 1, "language": "Go", "description": "A"})
    await database.upsert_watch_log(1, "owner/b", {"stars": 20, "forks": 2, "language": "Rust", "description": "B"})
    await database.upsert_watch_log(2, "owner/c", {"stars": 30, "forks": 3, "language": "TS", "description": "C"})
    logs_sub1 = await database.list_watch_logs_by_subscription(1)
    logs_sub2 = await database.list_watch_logs_by_subscription(2)
    assert len(logs_sub1) == 2
    assert len(logs_sub2) == 1
    names_sub1 = {log["full_name"] for log in logs_sub1}
    assert names_sub1 == {"owner/a", "owner/b"}


async def test_watch_log_get_missing(fresh_db):
    log = await database.get_watch_log(999, "nonexistent/repo")
    assert log is None
