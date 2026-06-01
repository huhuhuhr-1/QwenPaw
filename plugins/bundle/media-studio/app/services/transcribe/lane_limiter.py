"""Hard per-lane concurrency limits for transcribe (prevents capacity overrun)."""

from __future__ import annotations

import asyncio

from app.services.transcribe.lane_config import lane_configuration
from app.services.transcribe.lanes import normalize_transcribe_lane

_LANE_PRIORITY = ("fast", "slow", "external")


class TranscribeLaneLimiter:
    """Blocks until a slot is available on fast / bound / fallback lane."""

    def __init__(self) -> None:
        self._cond = asyncio.Condition()
        self._inflight: dict[str, int] = {lane: 0 for lane in _LANE_PRIORITY}

    def _lane_caps(self) -> dict[str, int]:
        caps: dict[str, int] = {}
        for lane in _LANE_PRIORITY:
            info = lane_configuration(lane)
            if info["enabled"] and info["available"]:
                caps[lane] = max(0, int(info["max_concurrent"]))
            else:
                caps[lane] = 0
        return caps

    def _try_take(self, lane: str, caps: dict[str, int]) -> bool:
        limit = caps.get(lane, 0)
        if limit <= 0:
            return False
        if self._inflight[lane] >= limit:
            return False
        self._inflight[lane] += 1
        return True

    def _try_pick_lane(self, bound_norm: str | None, caps: dict[str, int]) -> str | None:
        if self._try_take("fast", caps):
            return "fast"
        if bound_norm and self._try_take(bound_norm, caps):
            return bound_norm
        for lane in _LANE_PRIORITY:
            if lane != bound_norm and self._try_take(lane, caps):
                return lane
        return None

    async def acquire(self, bound: str | None) -> str:
        """Wait for capacity; prefer fast GPU when a fast slot exists."""
        bound_norm = normalize_transcribe_lane(bound) if bound else None
        while True:
            async with self._cond:
                caps = self._lane_caps()
                if not any(caps.values()):
                    raise RuntimeError("没有可用的转写队列容量")
                lane = self._try_pick_lane(bound_norm, caps)
                if lane:
                    return lane
                await self._cond.wait()

    async def release(self, lane: str) -> None:
        lane = normalize_transcribe_lane(lane)
        async with self._cond:
            self._inflight[lane] = max(0, self._inflight.get(lane, 0) - 1)
            self._cond.notify_all()

    def snapshot(self) -> dict[str, dict[str, int]]:
        """inflight / cap per lane (for tests and diagnostics)."""
        caps = self._lane_caps()
        return {
            lane: {
                "inflight": self._inflight.get(lane, 0),
                "capacity": caps.get(lane, 0),
            }
            for lane in _LANE_PRIORITY
        }
