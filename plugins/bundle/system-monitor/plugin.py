# -*- coding: utf-8 -*-
"""System Monitor Plugin for QwenPaw.

Provides real-time system metrics collection and visualization:
- CPU, Memory, Disk usage
- System handles and process info
- Configurable collection intervals

Uses the plugin startup hook to start the FastAPI backend and install skills.
"""

__all__ = ["plugin"]

import asyncio
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent
_PROCESS_NAME = "system-monitor"
_PROCESS_PORT = 7900


# ---------------------------------------------------------------------------
# Skill installation
# ---------------------------------------------------------------------------
_PLUGIN_SKILLS = ("sysmon",)


def _install_plugin_skills() -> None:
    """Copy plugin skills into the shared skill pool."""
    try:
        from qwenpaw.agents.skill_system import (
            get_skill_pool_dir,
            ensure_skill_pool_initialized,
        )
    except ImportError:
        logger.error("Cannot import skill_system; skill installation skipped")
        return

    try:
        ensure_skill_pool_initialized()
    except Exception as exc:
        logger.warning("Skill pool init failed: %s", exc)

    pool_dir = get_skill_pool_dir()
    skills_src = PLUGIN_DIR / "skills"

    for skill_name in _PLUGIN_SKILLS:
        src = skills_src / skill_name
        dst = pool_dir / skill_name
        if not src.exists():
            logger.warning("Plugin skill source missing: %s", src)
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        logger.info("Installed plugin skill to pool: %s", skill_name)

    _update_pool_manifest(pool_dir)


def _update_pool_manifest(pool_dir: Path) -> None:
    """Update skill.json manifest to include newly installed skills."""
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
        logger.warning("Failed to update pool manifest: %s", exc)


# ---------------------------------------------------------------------------
# Backend process management
# ---------------------------------------------------------------------------


def _is_backend_running() -> bool:
    """Check if the system-monitor backend is already running."""
    try:
        import httpx
        resp = httpx.get(f"http://localhost:{_PROCESS_PORT}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


async def _start_backend_async() -> asyncio.subprocess.Process:
    """Start the system-monitor FastAPI backend as a subprocess."""

    app_main = PLUGIN_DIR / "app" / "main.py"
    if not app_main.exists():
        logger.warning("system-monitor app/main.py not found, backend not started")
        return None

    env = os.environ.copy()
    env["SYSTEM_MONITOR_HOST"] = "127.0.0.1"
    env["SYSTEM_MONITOR_PORT"] = str(_PROCESS_PORT)

    import sys
    return await asyncio.subprocess.create_subprocess_exec(
        sys.executable, "-m", "app.main",
        cwd=str(PLUGIN_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _ensure_backend() -> None:
    """Ensure the system-monitor backend is running."""
    global _backend_proc
    if _is_backend_running():
        logger.info("System Monitor backend already running on port %d", _PROCESS_PORT)
        return

    logger.info("Starting System Monitor backend on port %d...", _PROCESS_PORT)
    _backend_proc = await _start_backend_async()
    if _backend_proc:
        await asyncio.sleep(3)  # Give startup time
        if _is_backend_running():
            logger.info("System Monitor backend started successfully")
        else:
            stdout, stderr = await _backend_proc.communicate()
            logger.error(
                "System Monitor backend failed to start.\nstdout: %s\nstderr: %s",
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

_backend_proc: asyncio.subprocess.Process | None = None


class SystemMonitorPlugin:
    """SystemMonitor plugin entry point."""

    def register(self, api):
        """Register all SystemMonitor components via startup hook."""
        api.register_startup_hook(
            hook_name="system_monitor_init",
            callback=self._on_startup,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name="system_monitor_cleanup",
            callback=self._on_shutdown,
            priority=50,
        )
        logger.info("SystemMonitor plugin registered hooks")

    async def _on_startup(self):
        """Initialize all SystemMonitor components on application startup."""
        logger.info("SystemMonitor plugin starting up...")

        logger.info("[SystemMonitor] Installing skills to pool...")
        _install_plugin_skills()

        logger.info("[SystemMonitor] Ensuring backend is running...")
        await _ensure_backend()

        logger.info("SystemMonitor plugin startup complete")

    async def _on_shutdown(self):
        """Cleanup on application shutdown."""
        logger.info("SystemMonitor plugin shutting down...")
        global _backend_proc
        if _backend_proc and _backend_proc.returncode is None:
            logger.info("Stopping System Monitor backend...")
            _backend_proc.terminate()
            try:
                await asyncio.wait_for(_backend_proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                _backend_proc.kill()
                await _backend_proc.wait()
            _backend_proc = None
            logger.info("System Monitor backend stopped")


plugin = SystemMonitorPlugin()
