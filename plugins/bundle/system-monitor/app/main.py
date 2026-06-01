# -*- coding: utf-8 -*-
"""System Monitor FastAPI Application."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_config
from app.db.sqlite import get_db
from app.routers import health, metrics, config_api
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.cleaner import cleanup_old_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("System Monitor starting...")
    load_config()
    get_db()  # Initialize database
    cleanup_old_data()
    start_scheduler()
    logger.info("System Monitor started on port %s", os.getenv("SYSTEM_MONITOR_PORT", 7900))
    yield
    # Shutdown
    stop_scheduler()
    logger.info("System Monitor stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="System Monitor API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(config_api.router, prefix="/api/config", tags=["config"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SYSTEM_MONITOR_PORT", 7900))
    uvicorn.run(app, host="0.0.0.0", port=port)
