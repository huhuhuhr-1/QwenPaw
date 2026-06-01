"""注册所有路由"""

from app.main import app


def register_routers(app):
    from app.routers.trending import router as trending_router
    from app.routers.repos import router as repos_router
    from app.routers.monitor import router as monitor_router
    from app.routers.reports import router as reports_router

    app.include_router(trending_router, prefix="/trending", tags=["trending"])
    app.include_router(repos_router, prefix="/repos", tags=["repos"])
    app.include_router(monitor_router, prefix="/monitor", tags=["monitor"])
    app.include_router(reports_router, prefix="/reports", tags=["reports"])
