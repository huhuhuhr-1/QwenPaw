"""Format model name and duration for artifact list."""

from __future__ import annotations

from datetime import datetime

from app.services.transcribe.lane_config import lane_configuration


def format_transcribe_run_model(lane: str) -> str:
    info = lane_configuration(lane)
    label = info.get("label") or lane
    backend = info.get("backend") or "local"
    if backend == "local":
        device = (info.get("device") or "cpu").upper()
        model = info.get("model_path") or "—"
        return f"{label} · {model} ({device})"
    if backend == "dashscope":
        model = info.get("dashscope_model") or "paraformer"
        return f"{label} · DashScope {model}"
    model = info.get("openai_model") or "whisper-1"
    return f"{label} · OpenAI {model}"


def format_step_run_model(step_type: str, *, lane: str | None = None) -> str:
    if step_type == "extract_audio":
        return "FFmpeg 抽音频"
    if step_type == "polish":
        return "MiniMax 文本精修"
    if step_type == "transcribe":
        if lane:
            return format_transcribe_run_model(lane)
        return "Whisper 转写"
    return step_type


def resolve_artifact_run_model(row: dict) -> str | None:
    if row.get("run_model"):
        return row["run_model"]
    step_type = row.get("step_type")
    if step_type == "transcribe":
        lane = row.get("transcribe_lane") or "slow"
        try:
            return format_transcribe_run_model(lane)
        except Exception:
            return format_step_run_model("transcribe", lane=lane)
    if step_type in ("extract_audio", "polish"):
        return format_step_run_model(step_type)
    return None


def duration_seconds(started_at: str | None, completed_at: str | None) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        sec = (end - start).total_seconds()
        return max(0.0, sec) if sec == sec else None
    except (ValueError, TypeError):
        return None
