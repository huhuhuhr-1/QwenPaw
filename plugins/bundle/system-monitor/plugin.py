# -*- coding: utf-8 -*-
"""System Monitor Plugin for QwenPaw —— Mode A

实时采集和展示主机 CPU、内存、磁盘、句柄、负载指标。

架构:Mode A —— FastAPI 路由直接挂在 QwenPaw 主服务,无子进程。
"""

__all__ = ["plugin"]

import logging
import shutil
import sys
from pathlib import Path

# QwenPaw loader 用 importlib + __package__ = "plugin_system_monitor",所以需要把
# 插件根目录加到 sys.path,然后用绝对 import 才能 import 到 sibling 包 sysmon
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

logger = logging.getLogger(__name__)


# ── Skill 安装 ─────────────────────────────────────────────────────

_PLUGIN_SKILLS = ("sysmon",)


def _install_plugin_skills() -> None:
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
    _PLUGIN_DIR = Path(__file__).resolve().parent
    skills_src = _PLUGIN_DIR / "skills"
    for skill_name in _PLUGIN_SKILLS:
        src = skills_src / skill_name
        dst = pool_dir / skill_name
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def _update_pool_manifest(pool_dir: Path) -> None:
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
                    "source": "plugin:system-monitor",
                    "protected": False,
                }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("更新 pool manifest 失败: %s", exc)


# ── Plugin 入口(Mode A 统一范式) ─────────────────────────────────

class SystemMonitorPlugin:
    def register(self, api) -> None:
        # 相对 import(loader 设了 __package__ = "plugin_system_monitor",
        # __path__ = [_PLUGIN_DIR])
        from sysmon.routers.metrics import router as metrics_router
        from sysmon.routers.health import router as health_router
        from sysmon.routers.config_api import router as config_router

        api.register_http_router(
            metrics_router, prefix="/metrics", tags=["system-monitor"],
        )
        api.register_http_router(
            health_router, prefix="/health", tags=["system-monitor"],
        )
        api.register_http_router(
            config_router, prefix="/config", tags=["system-monitor"],
        )
        _install_plugin_skills()
        logger.info("system-monitor registered (Mode A: 3 HTTP routers, no subprocess)")


plugin = SystemMonitorPlugin()
