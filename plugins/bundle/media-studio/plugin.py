# -*- coding: utf-8 -*-
"""Media Studio Plugin for QwenPaw.

Provides local data processing capabilities:
- Audio/Video transcription via Whisper / DashScope / OpenAI ASR
- Text polishing via MiniMax
- Video to audio extraction
- Multi-step workflow orchestration

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
_PROCESS_NAME = "media-studio"
_PROCESS_PORT = 7899


# ---------------------------------------------------------------------------
# Skill installation
# ---------------------------------------------------------------------------
_PLUGIN_SKILLS = ("transcribe", "polish", "media", "workflow")


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
                    "source": "plugin:media-studio",
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
    """Check if the media-studio backend is already running."""
    try:
        import httpx
        resp = httpx.get(f"http://localhost:{_PROCESS_PORT}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


async def _start_backend_async() -> asyncio.subprocess.Process:
    """Start the media-studio FastAPI backend as a subprocess."""

    # Detect if we're in dev mode (app/ exists next to plugin.py)
    app_main = PLUGIN_DIR / "app" / "main.py"
    if not app_main.exists():
        logger.warning("media-studio app/main.py not found, backend not started")
        return None

    env = os.environ.copy()
    env["MEDIA_STUDIO_HOST"] = "127.0.0.1"
    env["MEDIA_STUDIO_PORT"] = str(_PROCESS_PORT)

    import sys
    return await asyncio.subprocess.create_subprocess_exec(
        sys.executable, "-m", "app.main",
        cwd=str(PLUGIN_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _ensure_backend() -> None:
    """Ensure the media-studio backend is running."""
    global _backend_proc
    if _is_backend_running():
        logger.info("Media Studio backend already running on port %d", _PROCESS_PORT)
        return

    logger.info("Starting Media Studio backend on port %d...", _PROCESS_PORT)
    _backend_proc = await _start_backend_async()
    if _backend_proc:
        await asyncio.sleep(3)  # Give startup time
        if _is_backend_running():
            logger.info("Media Studio backend started successfully")
        else:
            stdout, stderr = await _backend_proc.communicate()
            logger.error(
                "Media Studio backend failed to start.\nstdout: %s\nstderr: %s",
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
            )


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

_backend_proc: asyncio.subprocess.Process | None = None


class MediaStudioPlugin:
    """MediaStudio plugin entry point."""

    def register(self, api):
        """Register all MediaStudio components via startup hook."""
        api.register_startup_hook(
            hook_name="media_studio_init",
            callback=self._on_startup,
            priority=50,
        )
        api.register_shutdown_hook(
            hook_name="media_studio_cleanup",
            callback=self._on_shutdown,
            priority=50,
        )
        logger.info("MediaStudio plugin registered hooks")

    async def _on_startup(self):
        """Initialize all MediaStudio components on application startup."""
        logger.info("MediaStudio plugin starting up...")

        logger.info("[MediaStudio] Installing skills to pool...")
        _install_plugin_skills()

        logger.info("[MediaStudio] Ensuring backend is running...")
        await _ensure_backend()

        logger.info("MediaStudio plugin startup complete")

    async def _on_shutdown(self):
        """Cleanup on application shutdown."""
        logger.info("MediaStudio plugin shutting down...")
        global _backend_proc
        if _backend_proc and _backend_proc.returncode is None:
            logger.info("Stopping Media Studio backend...")
            _backend_proc.terminate()
            try:
                await asyncio.wait_for(_backend_proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                _backend_proc.kill()
                await _backend_proc.wait()
            _backend_proc = None
            logger.info("Media Studio backend stopped")


plugin = MediaStudioPlugin()
