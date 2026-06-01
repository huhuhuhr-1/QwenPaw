from fastapi import APIRouter, HTTPException

from app.models.schemas import QueueControlResponse
from app.services.pipeline.engine import TRANSCRIBE_SCHEDULER_LANE, DagEngine
from app.services.pipeline.queue_control import LANE_TO_STEP, LEGACY_TRANSCRIBE_LANE, QueueController
from app.services.pipeline.queue_stats import get_global_queue_stats
from app.services.transcribe.lanes import SCHEDULER_LANES

router = APIRouter(prefix="/queues", tags=["queues"])


def _lanes_to_reschedule(lane: str) -> list[str]:
    if lane == LEGACY_TRANSCRIBE_LANE:
        return list(SCHEDULER_LANES)
    if lane in LANE_TO_STEP:
        return [lane]
    raise ValueError(f"unknown lane: {lane}")


@router.get("", response_model=QueueControlResponse)
async def get_queue_control():
    return QueueControlResponse(**QueueController.get_state())


@router.get("/stats")
async def queue_stats_with_control():
    return await get_global_queue_stats()


@router.post("/pause-all", response_model=QueueControlResponse)
async def pause_all_queues():
    QueueController.pause_all()
    return QueueControlResponse(**QueueController.get_state())


@router.post("/resume-all", response_model=QueueControlResponse)
async def resume_all_queues():
    QueueController.resume_all()
    from app.services.pipeline.engine import _SCHEDULER_CONCURRENCY

    for sched in list(_SCHEDULER_CONCURRENCY) + [TRANSCRIBE_SCHEDULER_LANE]:
        await DagEngine._schedule_runnable_steps(scheduler_lane=sched)
    return QueueControlResponse(**QueueController.get_state())


@router.post("/{lane}/pause", response_model=QueueControlResponse)
async def pause_lane(lane: str):
    try:
        QueueController.pause_lane(lane)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return QueueControlResponse(**QueueController.get_state())


@router.post("/{lane}/resume", response_model=QueueControlResponse)
async def resume_lane(lane: str):
    try:
        QueueController.resume_lane(lane)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    try:
        for sched in _lanes_to_reschedule(lane):
            await DagEngine._schedule_runnable_steps(scheduler_lane=sched)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return QueueControlResponse(**QueueController.get_state())
