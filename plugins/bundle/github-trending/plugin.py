# -*- coding: utf-8 -*-
"""GitHub Trend Hub —— GitHub 热榜数据管理插件"""

__all__ = ["plugin"]

import asyncio
import logging
import os
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent
_PROCESS_PORT = 7901
logger = logging.getLogger(__name__)

sys.path.insert(0, str(_PLUGIN_DIR))

from qwenpaw.plugins.api import PluginApi

from tools.trending import (
    trending_get_daily,
    trending_get_dates,
    trending_upload,
)
from tools.repos import (
    repo_search,
    repo_detail,
    repo_trend,
)
from tools.monitor import (
    monitor_list_subscriptions,
    monitor_subscribe,
    monitor_unsubscribe,
    monitor_get_events,
    monitor_upload,
)
from tools.reports import (
    report_upload,
    report_list,
)


class GitHubTrendingPlugin:
    def register(self, api: PluginApi) -> None:
        # ── 热榜工具 ──
        api.register_tool(
            tool_name="trending_get_daily",
            tool_func=trending_get_daily,
            description="获取每日 GitHub 热榜数据。参数: date(日期YYYY-MM-DD), language(语言筛选)",
            icon="🔥",
        )
        api.register_tool(
            tool_name="trending_get_dates",
            tool_func=trending_get_dates,
            description="获取有热榜数据的日期列表。参数: language(语言筛选)",
            icon="📅",
        )
        api.register_tool(
            tool_name="trending_upload",
            tool_func=trending_upload,
            description="上传热榜采集数据到存储。参数: date, language, summary, items(列表)",
            icon="📤",
        )

        # ── 仓库工具 ──
        api.register_tool(
            tool_name="repo_search",
            tool_func=repo_search,
            description="搜索 GitHub 仓库。参数: keyword(关键词), limit(数量限制)",
            icon="🔍",
        )
        api.register_tool(
            tool_name="repo_detail",
            tool_func=repo_detail,
            description="获取仓库详细信息。参数: full_name(owner/repo格式)",
            icon="💾",
        )
        api.register_tool(
            tool_name="repo_trend",
            tool_func=repo_trend,
            description="获取仓库历史趋势。参数: full_name(owner/repo格式)",
            icon="📈",
        )

        # ── 订阅监控工具 ──
        api.register_tool(
            tool_name="monitor_list_subscriptions",
            tool_func=monitor_list_subscriptions,
            description="获取订阅列表",
            icon="📡",
        )
        api.register_tool(
            tool_name="monitor_subscribe",
            tool_func=monitor_subscribe,
            description="订阅 GitHub 仓库。参数: repo(owner/repo格式)",
            icon="➕",
        )
        api.register_tool(
            tool_name="monitor_unsubscribe",
            tool_func=monitor_unsubscribe,
            description="取消订阅。参数: subscription_id",
            icon="➖",
        )
        api.register_tool(
            tool_name="monitor_get_events",
            tool_func=monitor_get_events,
            description="获取监控动态。参数: repo(可选), limit(数量)",
            icon="📋",
        )
        api.register_tool(
            tool_name="monitor_upload",
            tool_func=monitor_upload,
            description="上传监控数据。参数: repo, repo_info, events",
            icon="📤",
        )

        # ── 分析报告工具 ──
        api.register_tool(
            tool_name="report_upload",
            tool_func=report_upload,
            description="上传分析报告。参数: date, report_type, content",
            icon="📊",
        )
        api.register_tool(
            tool_name="report_list",
            tool_func=report_list,
            description="获取报告列表。参数: date(可选), limit(数量)",
            icon="📋",
        )

        api.register_startup_hook(
            hook_name="github_trending_startup",
            callback=self._on_startup,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name="github_trending_shutdown",
            callback=self._on_shutdown,
            priority=50,
        )

    async def _on_startup(self):
        """启动 GitHub Trend Hub FastAPI 后端子进程"""
        app_main = _PLUGIN_DIR / "app" / "main.py"
        if not app_main.exists():
            logger.warning("github-trending app/main.py not found, backend not started")
            return

        env = os.environ.copy()
        env["HOST"] = "127.0.0.1"
        env["PORT"] = str(_PROCESS_PORT)

        self._proc: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "app.main",
            cwd=str(_PLUGIN_DIR),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"github-trending backend started on port {_PROCESS_PORT}, pid={self._proc.pid}")

    async def _on_shutdown(self):
        """关闭 GitHub Trend Hub 后端子进程"""
        if getattr(self, "_proc", None) and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            logger.info("github-trending backend stopped")


plugin = GitHubTrendingPlugin()
