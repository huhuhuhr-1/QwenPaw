"""Read/write processor settings persisted in project .env."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, Settings

ENV_PATH = PROJECT_ROOT / ".env"

# field_name -> .env key (MEDIA_STUDIO_ prefix omitted where env uses it)
_MANAGED_KEYS: dict[str, str] = {
    "minimax_api_key": "MINIMAX_API_KEY",
    "transcribe_default_lane": "MEDIA_STUDIO_TRANSCRIBE_DEFAULT_LANE",
    "transcribe_fast_enabled": "MEDIA_STUDIO_TRANSCRIBE_FAST_ENABLED",
    "transcribe_slow_enabled": "MEDIA_STUDIO_TRANSCRIBE_SLOW_ENABLED",
    "transcribe_external_enabled": "MEDIA_STUDIO_TRANSCRIBE_EXTERNAL_ENABLED",
    "transcribe_fast_backend": "MEDIA_STUDIO_TRANSCRIBE_FAST_BACKEND",
    "transcribe_slow_backend": "MEDIA_STUDIO_TRANSCRIBE_SLOW_BACKEND",
    "transcribe_external_backend": "MEDIA_STUDIO_TRANSCRIBE_EXTERNAL_BACKEND",
    "transcribe_fast_model_path": "MEDIA_STUDIO_TRANSCRIBE_FAST_MODEL_PATH",
    "transcribe_fast_device": "MEDIA_STUDIO_TRANSCRIBE_FAST_DEVICE",
    "transcribe_slow_model_path": "MEDIA_STUDIO_TRANSCRIBE_SLOW_MODEL_PATH",
    "transcribe_slow_device": "MEDIA_STUDIO_TRANSCRIBE_SLOW_DEVICE",
    "transcribe_openai_api_key": "MEDIA_STUDIO_TRANSCRIBE_OPENAI_API_KEY",
    "transcribe_openai_base_url": "MEDIA_STUDIO_TRANSCRIBE_OPENAI_BASE_URL",
    "transcribe_openai_model": "MEDIA_STUDIO_TRANSCRIBE_OPENAI_MODEL",
    "dashscope_api_key": "DASHSCOPE_API_KEY",
    "dashscope_base_url": "MEDIA_STUDIO_DASHSCOPE_BASE_URL",
    "dashscope_asr_model": "MEDIA_STUDIO_DASHSCOPE_ASR_MODEL",
    "max_concurrent_transcribe_fast": "MEDIA_STUDIO_MAX_CONCURRENT_TRANSCRIBE_FAST",
    "max_concurrent_transcribe_slow": "MEDIA_STUDIO_MAX_CONCURRENT_TRANSCRIBE_SLOW",
    "max_concurrent_transcribe_external": "MEDIA_STUDIO_MAX_CONCURRENT_TRANSCRIBE_EXTERNAL",
}

_SECRET_FIELDS = frozenset(
    {
        "minimax_api_key",
        "transcribe_openai_api_key",
        "dashscope_api_key",
    }
)

_BOOL_FIELDS = frozenset(
    {
        "transcribe_fast_enabled",
        "transcribe_slow_enabled",
        "transcribe_external_enabled",
    }
)


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}****{value[-4:]}"


def get_public_config(settings: Any) -> dict:
    from app.services.transcribe.lane_config import (
        all_lane_configurations,
        available_lanes,
        lane_configuration,
    )

    default_lane = settings.transcribe_default_lane
    default_info = lane_configuration(default_lane)

    lanes_public = []
    for row in all_lane_configurations():
        item = dict(row)
        if row["backend"] == "openai":
            item["openai_api_key_set"] = bool(settings.transcribe_openai_api_key)
            item["openai_api_key_masked"] = _mask_secret(settings.transcribe_openai_api_key)
            item["openai_base_url"] = settings.transcribe_openai_base_url
            item["openai_model"] = settings.transcribe_openai_model
        if row["backend"] == "dashscope":
            item["dashscope_api_key_set"] = bool(settings.dashscope_api_key)
            item["dashscope_api_key_masked"] = _mask_secret(settings.dashscope_api_key)
            item["dashscope_base_url"] = settings.dashscope_base_url
            item["dashscope_model"] = settings.dashscope_asr_model
        lanes_public.append(item)

    from app.services.transcribe.local_models import scan_local_models

    return {
        "minimax_api_key_set": bool(settings.minimax_api_key),
        "minimax_api_key_masked": _mask_secret(settings.minimax_api_key),
        "env_file": str(ENV_PATH),
        "transcribe_default_lane": default_lane,
        "default_lane_available": default_info["available"],
        "available_transcribe_lanes": available_lanes(),
        "transcribe_lanes": lanes_public,
        "transcribe_pool_size": _transcribe_pool_size(),
        "available_local_models": scan_local_models(),
        "config_reload_hint": (
            "队列开关、后端、API Key、设备、模型路径保存后立即生效；"
            "转写 worker 总数增大也会自动扩容，缩小需重启 API。"
        ),
    }


def _transcribe_pool_size() -> int:
    from app.services.transcribe.pool import transcribe_pool_size

    return transcribe_pool_size()


def _parse_env_lines(text: str) -> list[str]:
    return text.splitlines() if text else []


def _upsert_env_line(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    out: list[str] = []
    found = False
    for line in lines:
        if pattern.match(line):
            if not found:
                out.append(f"{key}={value}")
                found = True
            continue
        out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    return out


def _serialize_field(field: str, val: Any) -> str:
    if field in _BOOL_FIELDS:
        return "true" if val else "false"
    if field in _SECRET_FIELDS:
        return str(val).strip()
    return str(val).strip() if isinstance(val, str) else str(int(val))


def write_env_updates(updates: dict[str, Any]) -> list[str]:
    """Write managed keys to .env; skip None and empty secrets (means unchanged)."""
    lines = _parse_env_lines(ENV_PATH.read_text(encoding="utf-8")) if ENV_PATH.exists() else []

    changed: list[str] = []
    for field, env_key in _MANAGED_KEYS.items():
        if field not in updates or updates[field] is None:
            continue
        val = updates[field]
        if field in _SECRET_FIELDS and isinstance(val, str) and not val.strip():
            continue
        str_val = _serialize_field(field, val)
        lines = _upsert_env_line(lines, env_key, str_val)
        os.environ[env_key] = str_val
        changed.append(env_key)

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return changed


def reload_settings() -> Any:
    """Reload Settings from disk and apply to running services."""
    import logging

    import app.config as config_module
    from app.services.pipeline.engine import DagEngine
    from app.services.polish.service import polish_service
    from app.services.transcribe.service import transcribe_service
    from app.services.transcribe.backends.registry import transcribe_registry

    logger = logging.getLogger(__name__)

    new_settings = Settings()
    config_module.settings = new_settings

    polish_service.init_client()

    transcribe_registry.unload_all()
    transcribe_service.unload()
    try:
        transcribe_service.load_model()
    except Exception:
        logger.warning(
            "transcribe warmup after config save failed; will load on next job",
            exc_info=True,
        )

    DagEngine.scheduler.apply_config_reload()
    logger.info(
        "runtime config reloaded (transcribe pool=%s)",
        _transcribe_pool_size(),
    )
    return new_settings
