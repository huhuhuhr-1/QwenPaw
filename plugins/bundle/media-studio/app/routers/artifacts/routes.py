from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.pagination import MAX_PAGE_SIZE
from app.models.schemas import (
    ArtifactListItem,
    ArtifactListResponse,
    BatchArtifactIdsRequest,
    StepType,
)
from app.services.artifacts.run_info import duration_seconds, resolve_artifact_run_model
from app.services.artifacts.service import (
    STEP_LABELS,
    artifact_download_url,
    build_artifacts_zip,
)
from app.services.shared.storage import db
from app.services.workflow.admin import WorkflowAdminError

router = APIRouter()


def _item(row: dict) -> ArtifactListItem:
    step_type = row["step_type"]
    file_id = row["file_id"]
    return ArtifactListItem(
        file_id=file_id,
        name=row["original_name"],
        file_type=row["file_type"],
        size_bytes=row["size_bytes"] or 0,
        step_type=StepType(step_type),
        step_label=STEP_LABELS.get(step_type, step_type),
        workflow_id=row["workflow_id"],
        source_name=row["source_name"] or "",
        completed_at=row.get("completed_at"),
        run_model=resolve_artifact_run_model(row),
        duration_seconds=duration_seconds(
            row.get("started_at"), row.get("completed_at")
        ),
        download_url=artifact_download_url(step_type, file_id),
    )


@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE, description="每页条数，最大 500"),
    step_type: str | None = Query(None, description="extract_audio | transcribe | polish"),
):
    if step_type and step_type not in ("extract_audio", "transcribe", "polish"):
        raise HTTPException(422, "invalid step_type")
    total = await db.count_artifacts(step_type=step_type)
    offset = (page - 1) * page_size
    rows = await db.list_artifacts(offset=offset, limit=page_size, step_type=step_type)
    return ArtifactListResponse(
        items=[_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/artifacts/batch-download")
async def batch_download_artifacts(req: BatchArtifactIdsRequest):
    try:
        data, filename = await build_artifacts_zip(req.file_ids)
    except WorkflowAdminError as e:
        raise HTTPException(e.status_code, e.message) from e
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
