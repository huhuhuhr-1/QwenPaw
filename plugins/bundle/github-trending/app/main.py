"""GitHub Trend Hub 后端服务"""

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
    yield
    logger.info("shutting down...")


app = FastAPI(
    title="GitHub Trend Hub",
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
