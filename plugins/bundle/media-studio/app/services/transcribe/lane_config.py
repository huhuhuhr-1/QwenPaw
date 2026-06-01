"""Transcribe lane availability: enabled + configured → routable."""

from __future__ import annotations

from app.services.transcribe.local_models import is_local_model_ready, scan_local_models
from app.services.transcribe.lanes import (
    DEFAULT_TRANSCRIBE_LANE,
    TRANSCRIBE_LANES,
    normalize_transcribe_lane,
)

_LANE_LABELS = {
    "fast": "转写·快 (GPU)",
    "slow": "转写·慢 (CPU)",
    "external": "转写·云端 (API)",
}

def _settings():
    from app.config import settings

    return settings


def _lane_enabled(lane: str) -> bool:
    cfg = _settings()
    lane = normalize_transcribe_lane(lane)
    return {
        "fast": cfg.transcribe_fast_enabled,
        "slow": cfg.transcribe_slow_enabled,
        "external": cfg.transcribe_external_enabled,
    }[lane]


def _lane_backend(lane: str) -> str:
    cfg = _settings()
    lane = normalize_transcribe_lane(lane)
    if lane == "fast":
        return cfg.transcribe_fast_backend.lower().strip()
    if lane == "slow":
        return cfg.transcribe_slow_backend.lower().strip()
    return cfg.transcribe_external_backend.lower().strip()


def _local_model_ready(model_path: str) -> tuple[bool, str]:
    if is_local_model_ready(model_path):
        return True, "本地模型已就绪（~/.cache/qwenpaw/models/）"
    available = scan_local_models()
    if not available:
        return False, "~/.cache/qwenpaw/models/ 目录下暂无已下载模型，请执行 scripts/download_whisper_model.py"
    return False, f"未找到模型「{model_path}」，请在配置页从已下载模型中选择"


def lane_configuration(lane: str) -> dict:
    """Per-lane status for UI and routing."""
    cfg = _settings()
    lane = normalize_transcribe_lane(lane)
    enabled = _lane_enabled(lane)
    backend = _lane_backend(lane)

    model_path = device = compute_type = api_key_set = None
    configured = False
    reason = ""

    if not enabled:
        reason = "队列已在配置中关闭"
    elif backend == "local":
        if lane == "fast":
            model_path = cfg.transcribe_fast_model_path
            device = cfg.transcribe_fast_device
            compute_type = cfg.transcribe_fast_compute_type
        else:
            model_path = cfg.transcribe_slow_model_path
            device = cfg.transcribe_slow_device
            compute_type = cfg.transcribe_slow_compute_type
        configured, reason = _local_model_ready(model_path)
    elif backend == "openai":
        api_key_set = bool(cfg.transcribe_openai_api_key)
        configured = api_key_set
        reason = "OpenAI API Key 已配置" if configured else "缺少 MEDIA_STUDIO_TRANSCRIBE_OPENAI_API_KEY"
    elif backend == "dashscope":
        api_key_set = bool(cfg.dashscope_api_key or cfg.transcribe_openai_api_key)
        configured = api_key_set
        reason = "DashScope Key 已配置" if configured else "缺少 DASHSCOPE_API_KEY"
    else:
        reason = f"未知后端类型: {backend}"

    available = enabled and configured

    return {
        "lane": lane,
        "label": _LANE_LABELS[lane],
        "scheduler_lane": f"transcribe_{lane}",
        "enabled": enabled,
        "backend": backend,
        "configured": configured,
        "available": available,
        "reason": reason,
        "model_path": model_path,
        "device": device,
        "compute_type": compute_type,
        "api_key_set": api_key_set,
        "max_concurrent": {
            "fast": cfg.max_concurrent_transcribe_fast,
            "slow": cfg.max_concurrent_transcribe_slow,
            "external": cfg.max_concurrent_transcribe_external,
        }[lane],
    }


def all_lane_configurations() -> list[dict]:
    return [lane_configuration(ln) for ln in TRANSCRIBE_LANES]


def available_lanes() -> list[str]:
    return [c["lane"] for c in all_lane_configurations() if c["available"]]


def assert_lane_available(lane: str) -> str:
    """Return normalized lane or raise ValueError with message."""
    lane = normalize_transcribe_lane(lane)
    info = lane_configuration(lane)
    if not info["available"]:
        avail = available_lanes()
        hint = f"可用队列: {', '.join(avail)}" if avail else "当前没有可用的转写队列，请在配置管理中启用并填写凭据"
        raise ValueError(f"转写队列「{info['label']}」不可用：{info['reason']}。{hint}")
    return lane


_LANE_PRIORITY = ("fast", "slow", "external")


def resolve_transcribe_lane(requested: str | None) -> str:
    """Pick lane; if requested/bound lane不可用则回落到默认或第一个可用队列。"""
    if requested:
        lane = normalize_transcribe_lane(requested)
        if lane_configuration(lane)["available"]:
            return lane

    cfg = _settings()
    default = normalize_transcribe_lane(cfg.transcribe_default_lane)
    if lane_configuration(default)["available"]:
        return default

    for lane in _LANE_PRIORITY:
        if lane_configuration(lane)["available"]:
            return lane

    raise ValueError(
        "没有可用的转写队列。请在「配置管理」中启用队列并配置模型路径或 API Key。"
    )
