"""In-memory queue lane pause flags (per worker pool)."""

from __future__ import annotations

LANE_TO_STEP: dict[str, str] = {
    "extract": "extract_audio",
    "transcribe_fast": "transcribe",
    "transcribe_slow": "transcribe",
    "transcribe_external": "transcribe",
    "polish": "polish",
}

# Legacy single transcribe lane control → all transcribe queues
LEGACY_TRANSCRIBE_LANE = "transcribe"

STEP_TO_LANES: dict[str, list[str]] = {
    "extract_audio": ["extract"],
    "transcribe": ["transcribe_fast", "transcribe_slow", "transcribe_external"],
    "polish": ["polish"],
}


class QueueController:
    _paused_lanes: set[str] = set()
    _pause_all: bool = False

    @classmethod
    def is_paused(cls, scheduler_lane: str) -> bool:
        if cls._pause_all:
            return True
        if scheduler_lane in cls._paused_lanes:
            return True
        if (
            scheduler_lane == LEGACY_TRANSCRIBE_LANE
            and LEGACY_TRANSCRIBE_LANE in cls._paused_lanes
        ):
            return True
        if scheduler_lane in (
            "transcribe_fast",
            "transcribe_slow",
            "transcribe_external",
        ) and LEGACY_TRANSCRIBE_LANE in cls._paused_lanes:
            return True
        return False

    @classmethod
    def get_state(cls) -> dict:
        lanes = dict(LANE_TO_STEP)
        lanes[LEGACY_TRANSCRIBE_LANE] = "transcribe"
        return {
            "pause_all": cls._pause_all,
            "lanes": {
                lane: {
                    "paused": cls._pause_all or cls.is_paused(lane),
                }
                for lane in lanes
            },
        }

    @classmethod
    def pause_lane(cls, lane: str) -> None:
        if lane not in LANE_TO_STEP and lane != LEGACY_TRANSCRIBE_LANE:
            raise ValueError(f"unknown lane: {lane}")
        cls._paused_lanes.add(lane)

    @classmethod
    def resume_lane(cls, lane: str) -> None:
        if lane not in LANE_TO_STEP and lane != LEGACY_TRANSCRIBE_LANE:
            raise ValueError(f"unknown lane: {lane}")
        cls._paused_lanes.discard(lane)

    @classmethod
    def pause_all(cls) -> None:
        cls._pause_all = True

    @classmethod
    def resume_all(cls) -> None:
        cls._pause_all = False
        cls._paused_lanes.clear()
