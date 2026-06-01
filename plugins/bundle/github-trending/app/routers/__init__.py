"""注册所有路由"""


def register_routers(app):
    """把 5 个子 router 挂到传入的 app(可以是 FastAPI app 或 APIRouter)。"""
    from app.routers.trending import router as trending_router
    from app.routers.repos import router as repos_router
    from app.routers.monitor import router as monitor_router
    from app.routers.reports import router as reports_router
    from app.routers.settings import router as settings_router

    app.include_router(trending_router, prefix="/trending", tags=["trending"])
    app.include_router(repos_router, prefix="/repos", tags=["repos"])
    app.include_router(monitor_router, prefix="/monitor", tags=["monitor"])
    app.include_router(reports_router, prefix="/reports", tags=["reports"])
    app.include_router(settings_router, prefix="/settings", tags=["settings"])
