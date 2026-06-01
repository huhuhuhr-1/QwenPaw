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
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent
_PLUGIN_ID = "media-studio"
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
# Dependency installation (persistent)
# ---------------------------------------------------------------------------


def _ensure_dependencies() -> bool:
    """Install plugin's declared dependencies to ``.deps/`` if missing.

    The deps directory is a subdirectory of PLUGIN_DIR, which lives under
    ``/app/working/plugins/<id>/`` — bind-mounted from the host.  This makes
    installed packages survive container recreation.

    Returns True if deps are ready, False if install failed (logged but not
    raised so other plugin hooks can still proceed).
    """
    deps_dir = PLUGIN_DIR / ".deps"
    marker = deps_dir / ".installed"

    if marker.exists():
        return True

    try:
        manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("[%s] Cannot read plugin.json: %s", _PLUGIN_ID, exc)
        return False

    deps = manifest.get("dependencies", [])
    if not deps:
        marker.write_text("no-deps\n", encoding="utf-8")
        return True

    deps_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "[%s] Installing %d dependencies to %s …",
        _PLUGIN_ID, len(deps), deps_dir,
    )

    try:
        proc = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--no-input", "--quiet",
                "--target", str(deps_dir),
                *deps,
            ],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        logger.error("[%s] pip install timed out after 300s", _PLUGIN_ID)
        return False
    except Exception as exc:
        logger.error("[%s] pip install raised: %s", _PLUGIN_ID, exc)
        return False

    if proc.returncode != 0:
        logger.error(
            "[%s] pip install failed (rc=%d): %s",
            _PLUGIN_ID, proc.returncode, proc.stderr[-2000:],
        )
        return False

    marker.write_text(
        f"installed at {time.time()} with {len(deps)} deps\n",
        encoding="utf-8",
    )
    logger.info("[%s] Dependencies installed successfully", _PLUGIN_ID)
    return True


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

    # Make plugin-installed packages importable in the subprocess
    deps_dir = PLUGIN_DIR / ".deps"
    if deps_dir.exists():
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{deps_dir}{os.pathsep}{existing_pp}" if existing_pp else str(deps_dir)
        )

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
            # Capture stderr with a timeout — never block forever if uvicorn
            # is still starting or has hung without exiting.
            try:
                stdout, stderr = await asyncio.wait_for(
                    _backend_proc.communicate(),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Media Studio backend failed to start within 5s of "
                    "post-sleep health check; still running but unreachable"
                )
                stdout, stderr = b"", b"<timeout>"
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

        logger.info("[MediaStudio] Ensuring dependencies are installed...")
        _ensure_dependencies()

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
