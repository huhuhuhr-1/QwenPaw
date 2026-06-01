"""Global pipeline queue snapshot for the task list UI."""

from datetime import datetime, timezone

from app.config import settings
from app.services.pipeline.engine import DagEngine, TRANSCRIBE_SCHEDULER_LANE, _SCHEDULER_CONCURRENCY
from app.services.transcribe.pool import transcribe_pool_size
from app.services.pipeline.queue_control import QueueController
from app.services.shared.storage import db
from app.services.transcribe.lane_config import lane_configuration

_STEP_API_KEYS = {
    "extract_audio": "extract",
    "polish": "polish",
}

_TRANSCRIBE_LANE_API = {
    "fast": "transcribe_fast",
    "slow": "transcribe_slow",
    "external": "transcribe_external",
}

_STEP_LABELS = {
    "extract": "抽音频",
    "transcribe_fast": "转写·快 (GPU)",
    "transcribe_slow": "转写·慢 (CPU)",
    "transcribe_external": "转写·云端 (API)",
    "polish": "精修",
}


def _empty_lane() -> dict:
    return {
        "running": 0,
        "queued": 0,
        "waiting_deps": 0,
        "completed": 0,
        "failed": 0,
        "buffer": 0,
        "capacity": 0,
        "enabled": True,
        "available": True,
    }


async def get_global_queue_stats() -> dict:
    status_rows = await db.count_steps_by_type_and_status()
    transcribe_status = await db.count_transcribe_by_lane_and_status()
    queued_rows = await db.count_runnable_pending_by_type()
    transcribe_queued = await db.count_runnable_pending_transcribe_by_lane()
    waiting_rows = await db.count_waiting_deps_pending_by_type()
    transcribe_waiting = await db.count_waiting_deps_transcribe_by_lane()
    buffer = DagEngine.scheduler.queue_sizes()

    lane_keys = list(_STEP_API_KEYS.values()) + list(_TRANSCRIBE_LANE_API.values())
    lanes: dict[str, dict] = {key: _empty_lane() for key in lane_keys}

    for row in status_rows:
        api_key = _STEP_API_KEYS.get(row["step_type"])
        if not api_key:
            continue
        status = row["status"]
        count = row["count"]
        lane = lanes[api_key]
        if status == "processing":
            lane["running"] = count
        elif status == "completed":
            lane["completed"] = count
        elif status == "failed":
            lane["failed"] = count
        elif status == "cancelled":
            lane["failed"] += count

    for row in transcribe_status:
        api_key = _TRANSCRIBE_LANE_API.get(row["transcribe_lane"], "transcribe_slow")
        status = row["status"]
        count = row["count"]
        lane = lanes[api_key]
        if status == "processing":
            lane["running"] = count
        elif status == "completed":
            lane["completed"] = count
        elif status == "failed":
            lane["failed"] = count
        elif status == "cancelled":
            lane["failed"] += count

    for row in queued_rows:
        api_key = _STEP_API_KEYS.get(row["step_type"])
        if api_key:
            lanes[api_key]["queued"] = row["count"]

    for row in transcribe_queued:
        api_key = _TRANSCRIBE_LANE_API.get(row["transcribe_lane"], "transcribe_slow")
        lanes[api_key]["queued"] = row["count"]

    for row in waiting_rows:
        api_key = _STEP_API_KEYS.get(row["step_type"])
        if api_key:
            lanes[api_key]["waiting_deps"] = row["count"]

    for row in transcribe_waiting:
        api_key = _TRANSCRIBE_LANE_API.get(row["transcribe_lane"], "transcribe_slow")
        lanes[api_key]["waiting_deps"] = row["count"]

    for scheduler_lane, setting_name in _SCHEDULER_CONCURRENCY.items():
        api_key = _STEP_API_KEYS.get(scheduler_lane)
        if api_key:
            lanes[api_key]["capacity"] = max(1, getattr(settings, setting_name))
            lanes[api_key]["buffer"] = buffer.get(scheduler_lane, 0)
            lanes[api_key]["enabled"] = True
            lanes[api_key]["available"] = True

    labels = dict(_STEP_LABELS)
    pool = transcribe_pool_size()
    shared_buffer = buffer.get(TRANSCRIBE_SCHEDULER_LANE, 0) if pool > 0 else 0
    for config_lane, api_key in _TRANSCRIBE_LANE_API.items():
        info = lane_configuration(config_lane)
        enabled = bool(info["enabled"])
        available = bool(info["available"])
        lanes[api_key]["enabled"] = enabled
        lanes[api_key]["available"] = available
        lanes[api_key]["capacity"] = info["max_concurrent"] if enabled else 0
        lanes[api_key]["buffer"] = shared_buffer if enabled and pool > 0 else 0
        labels[api_key] = info["label"]

    control = QueueController.get_state()
    for config_lane, api_key in _TRANSCRIBE_LANE_API.items():
        if api_key in control.get("lanes", {}):
            control["lanes"][api_key]["enabled"] = lanes[api_key]["enabled"]

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "queues": lanes,
        "labels": labels,
        "control": control,
        "transcribe_pool_size": pool,
    }
