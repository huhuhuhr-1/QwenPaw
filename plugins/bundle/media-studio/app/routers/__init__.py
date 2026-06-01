"""HTTP 路由按业务模块分包，见各子目录 routes.py。"""

from fastapi import FastAPI

from app.routers import (
    artifacts,
    config,
    files,
    logs,
    media,
    polish,
    queue,
    transcribe,
    upload,
    workflow,
)


def register_routers(app: FastAPI) -> None:
    app.include_router(files.router, tags=["files"])
    app.include_router(upload.router, tags=["upload"])
    app.include_router(media.router, tags=["audio"])
    app.include_router(transcribe.router, tags=["document"])
    app.include_router(polish.router, tags=["polish"])
    app.include_router(workflow.router, tags=["workflow"])
    app.include_router(artifacts.router, tags=["artifacts"])
    app.include_router(queue.router)
    app.include_router(config.router)
    app.include_router(logs.router)


__all__ = ["register_routers"]
