from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.shared.storage import db
from app.services.pipeline.engine import DagEngine
from app.services.workflow.admin import (
    WorkflowAdminError,
    delete_workflow,
    delete_workflows_batch,
    build_workflows_zip,
)
from app.models.schemas import (
    CreateWorkflowRequest, WorkflowResponse, WorkflowListItem,
    WorkflowResultsResponse, WorkflowResultFile, StepResponse,
    StepActionResponse, StepType,
    BatchWorkflowIdsRequest, WorkflowDeleteResult, BatchDeleteResponse,
    WorkflowListResponse, GlobalQueueStatsResponse, QueueLaneStats,
    WorkflowControlResponse, BatchWorkflowControlResponse,
)
from app.pagination import MAX_PAGE_SIZE
from app.services.pipeline.queue_stats import get_global_queue_stats

router = APIRouter()


def _build_step_response(s: dict) -> StepResponse:
    return StepResponse(
        id=s["id"],
        step_type=StepType(s["step_type"]),
        status=s["status"],
        input_file_id=s.get("input_file_id") or None,
        output_file_id=s.get("output_file_id"),
        depends_on=s.get("depends_on"),
        error=s.get("error"),
        started_at=s.get("started_at"),
        completed_at=s.get("completed_at"),
        created_at=s.get("created_at", ""),
    )


@router.post("/workflows", status_code=201)
async def create_workflow(req: CreateWorkflowRequest):
    file_info = await db.get_file(req.file_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {req.file_id}")

    entry_type = file_info["file_type"]
    if entry_type not in ("video", "audio", "markdown"):
        raise HTTPException(422, f"unsupported entry type: {entry_type}")

    try:
        wf = await DagEngine.create_workflow(req.file_id, entry_type, req.name)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if not wf:
        raise HTTPException(500, "workflow creation failed")

    steps = await db.get_workflow_steps(wf["id"])
    entry_file = await db.get_file(wf["entry_file_id"])

    return WorkflowResponse(
        workflow_id=wf["id"],
        name=wf.get("name"),
        entry_file_id=wf["entry_file_id"],
        entry_type=wf["entry_type"],
        entry_file_name=entry_file["original_name"] if entry_file else "",
        status=wf["status"],
        transcribe_lane=wf.get("transcribe_lane"),
        steps=[_build_step_response(s) for s in steps],
        created_at=wf.get("created_at", ""),
    )


async def _workflow_list_items(workflows: list[dict]) -> list[WorkflowListItem]:
    result = []
    for wf in workflows:
        steps = await db.get_workflow_steps(wf["id"])
        entry_file = await db.get_file(wf["entry_file_id"])
        result.append(WorkflowListItem(
            workflow_id=wf["id"],
            name=wf.get("name"),
            entry_type=wf["entry_type"],
            entry_file_name=entry_file["original_name"] if entry_file else "",
            status=wf["status"],
            transcribe_lane=wf.get("transcribe_lane"),
            step_count=len(steps),
            completed_count=sum(1 for s in steps if s["status"] == "completed"),
            created_at=wf.get("created_at", ""),
        ))
    return result


@router.get("/workflows/queue-stats", response_model=GlobalQueueStatsResponse)
async def workflow_queue_stats():
    raw = await get_global_queue_stats()
    return GlobalQueueStatsResponse(
        updated_at=raw["updated_at"],
        labels=raw["labels"],
        queues={k: QueueLaneStats(**v) for k, v in raw["queues"].items()},
        control=raw.get("control", {}),
    )


@router.post("/workflows/{workflow_id}/pause", response_model=WorkflowControlResponse)
async def pause_workflow(workflow_id: str):
    try:
        n = await DagEngine.pause_workflow(workflow_id)
        wf = await db.get_workflow(workflow_id)
        return WorkflowControlResponse(
            workflow_id=workflow_id, status=wf["status"], affected_steps=n
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowControlResponse)
async def resume_workflow(workflow_id: str):
    try:
        n = await DagEngine.resume_workflow(workflow_id)
        wf = await db.get_workflow(workflow_id)
        return WorkflowControlResponse(
            workflow_id=workflow_id, status=wf["status"], affected_steps=n
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/workflows/batch-pause", response_model=BatchWorkflowControlResponse)
async def batch_pause_workflows(req: BatchWorkflowIdsRequest):
    result = await DagEngine.pause_workflows_batch(req.workflow_ids)
    return BatchWorkflowControlResponse(**result)


@router.post("/workflows/batch-resume", response_model=BatchWorkflowControlResponse)
async def batch_resume_workflows(req: BatchWorkflowIdsRequest):
    result = await DagEngine.resume_workflows_batch(req.workflow_ids)
    return BatchWorkflowControlResponse(**result)


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE, description="每页条数，最大 500"),
):
    total = await db.count_workflows()
    offset = (page - 1) * page_size
    workflows = await db.list_workflows(offset=offset, limit=page_size)
    items = await _workflow_list_items(workflows)
    return WorkflowListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    wf = await db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, f"workflow not found: {workflow_id}")

    steps = await db.get_workflow_steps(workflow_id)
    entry_file = await db.get_file(wf["entry_file_id"])

    return WorkflowResponse(
        workflow_id=wf["id"],
        name=wf.get("name"),
        entry_file_id=wf["entry_file_id"],
        entry_type=wf["entry_type"],
        entry_file_name=entry_file["original_name"] if entry_file else "",
        status=wf["status"],
        transcribe_lane=wf.get("transcribe_lane"),
        steps=[_build_step_response(s) for s in steps],
        created_at=wf.get("created_at", ""),
    )


@router.get("/workflows/{workflow_id}/results")
async def get_workflow_results(workflow_id: str):
    wf = await db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, f"workflow not found: {workflow_id}")

    steps = await db.get_workflow_steps(workflow_id)
    files = []

    step_type_to_url = {
        "extract_audio": "/audio/",
        "transcribe": "/document/",
        "polish": "/polished/",
    }

    for s in steps:
        if s.get("output_file_id") and s["status"] == "completed":
            out_file = await db.get_file(s["output_file_id"])
            if out_file:
                files.append(WorkflowResultFile(
                    file_id=s["output_file_id"],
                    step_type=StepType(s["step_type"]),
                    name=out_file["original_name"],
                    size_bytes=out_file["size_bytes"],
                    download_url=f"{step_type_to_url.get(s['step_type'], '/document/')}{s['output_file_id']}",
                ))

    return WorkflowResultsResponse(workflow_id=workflow_id, files=files)


@router.get("/steps/{step_id}")
async def get_step(step_id: str):
    step = await db.get_step(step_id)
    if not step:
        raise HTTPException(404, f"step not found: {step_id}")
    return _build_step_response(step)


@router.get("/workflows/{workflow_id}/logs")
async def get_workflow_logs(workflow_id: str):
    wf = await db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, f"workflow not found: {workflow_id}")
    return await db.get_workflow_logs(workflow_id)


@router.get("/steps/{step_id}/logs")
async def get_step_logs(step_id: str):
    step = await db.get_step(step_id)
    if not step:
        raise HTTPException(404, f"step not found: {step_id}")
    logs = await db.get_step_logs(step_id)
    return logs


@router.post("/steps/{step_id}/retry")
async def retry_step(step_id: str):
    step = await db.get_step(step_id)
    if not step:
        raise HTTPException(404, f"step not found: {step_id}")
    if step["status"] != "failed":
        raise HTTPException(422, "only failed steps can be retried")

    try:
        count = await DagEngine.retry_step(step_id)
        return StepActionResponse(step_id=step_id, status="pending", affected_count=count)
    except Exception as e:
        raise HTTPException(500, f"retry failed: {e}")


@router.delete("/workflows/{workflow_id}", response_model=WorkflowDeleteResult)
async def remove_workflow(workflow_id: str, force: bool = False):
    try:
        result = await delete_workflow(workflow_id, force=force)
        return WorkflowDeleteResult(**result)
    except WorkflowAdminError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/workflows/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_workflows(req: BatchWorkflowIdsRequest, force: bool = False):
    result = await delete_workflows_batch(req.workflow_ids, force=force)
    return BatchDeleteResponse(**result)


@router.get("/workflows/{workflow_id}/export")
async def export_workflow(workflow_id: str):
    wf = await db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, f"workflow not found: {workflow_id}")
    try:
        data, filename = await build_workflows_zip([workflow_id])
    except WorkflowAdminError as e:
        raise HTTPException(e.status_code, e.message) from e
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/workflows/batch-export")
async def batch_export_workflows(req: BatchWorkflowIdsRequest):
    try:
        data, filename = await build_workflows_zip(req.workflow_ids)
    except WorkflowAdminError as e:
        raise HTTPException(e.status_code, e.message) from e
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/steps/{step_id}/cancel")
async def cancel_step(step_id: str):
    step = await db.get_step(step_id)
    if not step:
        raise HTTPException(404, f"step not found: {step_id}")
    if step["status"] != "processing":
        raise HTTPException(422, "only processing steps can be cancelled")

    try:
        count = await DagEngine.cancel_step(step_id)
        return StepActionResponse(step_id=step_id, status="cancelled", affected_count=count)
    except Exception as e:
        raise HTTPException(500, f"cancel failed: {e}")
