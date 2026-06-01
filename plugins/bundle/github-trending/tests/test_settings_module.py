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


async def test_get_runtime_settings_caches_within_ttl(monkeypatch):
    """Within 60s TTL, the same cached dict is returned (no DB call)."""
    call_count = {"n": 0}

    async def mock_list():
        call_count["n"] += 1
        return {"collect_interval_min": "60"}

    monkeypatch.setattr(settings_mod, "list_settings", mock_list)
    cfg1 = await settings_mod.get_runtime_settings()
    cfg2 = await settings_mod.get_runtime_settings()
    cfg3 = await settings_mod.get_runtime_settings()
    assert cfg1 is cfg2 is cfg3  # same object — proves cache hit
    assert call_count["n"] == 1  # only one DB call across 3 reads


async def test_clear_cache_forces_reload(monkeypatch):
    """clear_cache() forces next call to re-read from DB."""
    call_count = {"n": 0}

    async def mock_list():
        call_count["n"] += 1
        return {}

    monkeypatch.setattr(settings_mod, "list_settings", mock_list)
    await settings_mod.get_runtime_settings()
    await settings_mod.get_runtime_settings()
    settings_mod.clear_cache()
    await settings_mod.get_runtime_settings()
    assert call_count["n"] == 2  # cache cleared once, third call re-reads
