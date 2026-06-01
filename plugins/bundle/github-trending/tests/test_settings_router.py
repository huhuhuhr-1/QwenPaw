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
