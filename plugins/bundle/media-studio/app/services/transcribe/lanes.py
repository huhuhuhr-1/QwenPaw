"""Transcribe queue lanes: fast / slow / external."""

from __future__ import annotations

TRANSCRIBE_LANES = frozenset({"fast", "slow", "external"})
DEFAULT_TRANSCRIBE_LANE = "fast"

SCHEDULER_LANES = (
    "transcribe_fast",
    "transcribe_slow",
    "transcribe_external",
)

_LANE_TO_SCHEDULER = {
    "fast": "transcribe_fast",
    "slow": "transcribe_slow",
    "external": "transcribe_external",
}

_SCHEDULER_TO_LANE = {v: k for k, v in _LANE_TO_SCHEDULER.items()}


def normalize_transcribe_lane(lane: str | None) -> str:
    if lane is None or lane == "":
        return DEFAULT_TRANSCRIBE_LANE
    lane = lane.lower().strip()
    if lane not in TRANSCRIBE_LANES:
        raise ValueError(f"invalid transcribe_lane: {lane!r} (use fast, slow, external)")
    return lane


def lane_to_scheduler_queue(lane: str) -> str:
    return _LANE_TO_SCHEDULER[normalize_transcribe_lane(lane)]


def scheduler_queue_to_lane(scheduler_lane: str) -> str | None:
    return _SCHEDULER_TO_LANE.get(scheduler_lane)
