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


@pytest.fixture(autouse=True)
def reset_trigger_tasks():
    """Clean module-level _TRIGGER_TASKS between tests."""
    from app.routers import settings as r
    original = dict(r._TRIGGER_TASKS)
    r._TRIGGER_TASKS.clear()
    yield
    r._TRIGGER_TASKS.clear()
    r._TRIGGER_TASKS.update(original)


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
    """When a collect task is running, POST returns 409."""
    from app.routers import settings as r
    r._TRIGGER_TASKS["existing"] = {"status": "running", "started_at": 0.0}
    with patch("app.routers.settings.collect_once", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/settings/trigger-collect")
    assert resp.status_code == 409
    assert "collect already running" in resp.json()["detail"]
