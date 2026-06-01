"""GitHub Trend Hub 后端服务"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import register_routers
from app.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up...")
    await init_db()

    # 启动 trending collector 后台任务
    collector_task: asyncio.Task | None = None
    if settings.collect_enabled:
        from app.collector import run_collector_loop
        collector_task = asyncio.create_task(
            run_collector_loop(),
            name="github-trending-collector",
        )
        logger.info(
            "Trending collector started: interval=%d min, languages=%s, period=%s",
            settings.collect_interval_min,
            settings.collect_languages,
            settings.collect_period,
        )
    else:
        logger.info("Trending collector disabled by config")

    try:
        yield
    finally:
        if collector_task is not None:
            collector_task.cancel()
            try:
                await collector_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning("Collector task ended with: %s", e)
        logger.info("shutting down...")


app = FastAPI(
    title="GitHub Trend Hub",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # 认证走 Authorization: Bearer,不需要 cookies;allow_credentials=True
    # 与 allow_origins=["*"] 组合会被浏览器拒,与本插件无关。
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "github-trending"}


def run():
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    run()
