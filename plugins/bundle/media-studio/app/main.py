import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.shared.storage import db
from app.services.transcribe.service import transcribe_service
from app.services.transcribe.pool import transcribe_pool_size
from app.services.polish.service import polish_service
from app.services.pipeline.engine import DagEngine
from app.routers import register_routers
from app.logging_filters import install_uvicorn_log_filters


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
install_uvicorn_log_filters()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up...")

    # 1. Init database
    await db.init()
    logger.info("database ready")

    # 2. Init storage directories
    import os
    os.makedirs(f"{settings.data_dir}/files", exist_ok=True)

    # 3. Transcribe: lazy-load models on first job (avoid blocking startup on large downloads)
    logger.info(
        "transcribe backends: fast=%s slow=%s external=%s (lazy load)",
        settings.transcribe_fast_backend,
        settings.transcribe_slow_backend,
        settings.transcribe_external_backend,
    )

    # 4. Init MiniMax client
    polish_service.init_client()
    if polish_service.client:
        logger.info("MiniMax client initialized")
    else:
        logger.warning("MINIMAX_API_KEY not set, polish will be unavailable")

    # 5. Start FIFO step workers
    DagEngine.scheduler.ensure_workers()

    # 6. Recovery scan for interrupted steps
    await DagEngine.recovery_scan()
    logger.info("recovery scan complete")

    yield

    # Shutdown
    logger.info("shutting down...")
    transcribe_service.unload()
    await db.close()
    logger.info("shutdown complete")


app = FastAPI(
    title="Media Studio",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "concurrency": {
            "extract": settings.max_concurrent_extract,
            "transcribe_pool": transcribe_pool_size(),
            "polish": settings.max_concurrent_polish,
        },
        "transcribe_default_lane": settings.transcribe_default_lane,
    }


def run():
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
