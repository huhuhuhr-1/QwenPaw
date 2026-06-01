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
