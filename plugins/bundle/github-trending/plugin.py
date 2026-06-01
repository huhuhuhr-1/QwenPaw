# -*- coding: utf-8 -*-
"""GitHub Trend Hub —— GitHub 热榜数据管理插件

架构:Mode A —— 把 FastAPI 路由直接注册到 QwenPaw 主服务,不启子进程。
前端 host.getApiUrl() 拿的是主进程 URL(/api/trending/...),模式 A 直接匹配,
不需要任何反向代理。
"""

__all__ = ["plugin"]

import asyncio
import logging
import shutil
import sys
from pathlib import Path

# ``qwenpaw plugin install`` execs this file as a plain module (no
# package), so sibling modules are not reachable via relative imports
# unless the plugin directory is on sys.path before importing them.
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

logger = logging.getLogger(__name__)

from fastapi import APIRouter  # noqa: E402
from qwenpaw.plugins.api import PluginApi  # noqa: E402

from app.routers.trending import router as trending_router  # noqa: E402
from app.routers.repos import router as repos_router  # noqa: E402
from app.routers.monitor import router as monitor_router  # noqa: E402
from app.routers.reports import router as reports_router  # noqa: E402
from app.routers.settings import router as settings_router  # noqa: E402

from tools.trending import trending_get_daily, trending_get_dates  # noqa: E402
from tools.repos import repo_search, repo_detail, repo_trend  # noqa: E402
from tools.monitor import (  # noqa: E402
    monitor_list_subscriptions,
    monitor_get_events,
)
from tools.reports import report_list  # noqa: E402


# ── Skill 安装 ─────────────────────────────────────────────────────

_PLUGIN_SKILLS = ("github-trending",)


def _install_plugin_skills() -> None:
    """将插件 skills 复制到共享 skill pool。"""
    try:
        from qwenpaw.agents.skill_system import (
            get_skill_pool_dir,
            ensure_skill_pool_initialized,
        )
    except ImportError:
        logger.error("无法导入 skill_system,跳过 skill 安装")
        return

    try:
        ensure_skill_pool_initialized()
    except Exception as exc:
        logger.warning("Skill pool 初始化失败: %s", exc)

    pool_dir = get_skill_pool_dir()
    skills_src = _PLUGIN_DIR / "skills"

    for skill_name in _PLUGIN_SKILLS:
        src = skills_src / skill_name
        dst = pool_dir / skill_name
        if not src.exists():
            logger.warning("插件 skill 源缺失: %s", src)
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        logger.info("已安装插件 skill 到 pool: %s", skill_name)

    _update_pool_manifest(pool_dir)


def _update_pool_manifest(pool_dir: Path) -> None:
    """更新 skill.json manifest,注册新安装的 skills。"""
    import json

    manifest_path = pool_dir / "skill.json"
    try:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"skills": {}, "builtin_skill_names": []}

        skills = manifest.setdefault("skills", {})
        for skill_name in _PLUGIN_SKILLS:
            if skill_name not in skills:
                skills[skill_name] = {
                    "source": "plugin:github-trending",
                    "protected": False,
                }

        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("更新 pool manifest 失败: %s", exc)


# ── 后台 collector(在主进程里跑) ────────────────────────────────

_collector_task: asyncio.Task | None = None


async def _start_collector() -> None:
    """主进程 lifespan 调:把 collector 后台循环拉起来。"""
    global _collector_task
    try:
        from app.config import settings
        from app.database import init_db
        from app.collector import run_collector_loop

        if not settings.collect_enabled:
            logger.info("[github-trending] collector disabled by config")
            return

        await init_db()
        _collector_task = asyncio.create_task(
            run_collector_loop(),
            name="github-trending-collector",
        )
        logger.info(
            "[github-trending] collector started: interval=%d min, languages=%s",
            settings.collect_interval_min,
            settings.collect_languages,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[github-trending] failed to start collector: %s", exc)


async def _stop_collector() -> None:
    """主进程 shutdown 调:取消 collector task。"""
    global _collector_task
    if _collector_task is None:
        return
    _collector_task.cancel()
    try:
        await _collector_task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("[github-trending] collector task ended with: %s", exc)
    _collector_task = None
    logger.info("[github-trending] collector stopped")


# ── Plugin 入口 ────────────────────────────────────────────────────

class GitHubTrendingPlugin:
    def register(self, api: PluginApi) -> None:
        # 1. 注册只读工具(给 Agent 用)
        api.register_tool(
            tool_name="trending_get_daily",
            tool_func=trending_get_daily,
            description="获取每日热榜。参数: date, language",
            icon="🔥",
        )
        api.register_tool(
            tool_name="trending_get_dates",
            tool_func=trending_get_dates,
            description="获取有数据的日期列表。参数: language",
            icon="📅",
        )
        api.register_tool(
            tool_name="repo_search",
            tool_func=repo_search,
            description="搜索仓库。参数: keyword, limit",
            icon="🔍",
        )
        api.register_tool(
            tool_name="repo_detail",
            tool_func=repo_detail,
            description="获取仓库详情。参数: full_name",
            icon="📦",
        )
        api.register_tool(
            tool_name="repo_trend",
            tool_func=repo_trend,
            description="获取仓库历史趋势。参数: full_name",
            icon="📈",
        )
        api.register_tool(
            tool_name="monitor_list_subscriptions",
            tool_func=monitor_list_subscriptions,
            description="获取订阅列表",
            icon="📋",
        )
        api.register_tool(
            tool_name="monitor_get_events",
            tool_func=monitor_get_events,
            description="获取监控动态。参数: repo, limit",
            icon="📡",
        )
        api.register_tool(
            tool_name="report_list",
            tool_func=report_list,
            description="获取报告列表。参数: date, limit",
            icon="📊",
        )

        # 2. Mode A:每个子 router 单独挂,prefix 对应前端调用路径
        # 之前尝试用一个 APIRouter + register_routers 会有双重 prefix 问题
        api.register_http_router(
            trending_router, prefix="/trending", tags=["github-trending"],
        )
        api.register_http_router(
            repos_router, prefix="/repos", tags=["github-trending"],
        )
        api.register_http_router(
            monitor_router, prefix="/monitor", tags=["github-trending"],
        )
        api.register_http_router(
            reports_router, prefix="/reports", tags=["github-trending"],
        )
        api.register_http_router(
            settings_router, prefix="/settings", tags=["github-trending"],
        )

        # 3. 后台 collector 在主进程跑(不再起子进程)
        api.register_startup_hook(
            hook_name="github_trending_start_collector",
            callback=_start_collector,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name="github_trending_stop_collector",
            callback=_stop_collector,
            priority=50,
        )

        # 4. 同步 skills(只是文件复制,无副作用)
        _install_plugin_skills()


plugin = GitHubTrendingPlugin()
