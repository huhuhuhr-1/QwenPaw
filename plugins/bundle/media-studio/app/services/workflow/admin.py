"""Workflow administration: delete, export."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import HTTPException

from app.services.shared.storage import db, storage
from app.services.shared.zip_flat import flat_arc_name


class WorkflowAdminError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def _collect_workflow_file_ids(workflow_id: str) -> set[str]:
    wf = await db.get_workflow(workflow_id)
    if not wf:
        return set()
    ids: set[str] = {wf["entry_file_id"]}
    for step in await db.get_workflow_steps(workflow_id):
        if step.get("input_file_id"):
            ids.add(step["input_file_id"])
        if step.get("output_file_id"):
            ids.add(step["output_file_id"])
    return {x for x in ids if x}


async def delete_workflow(workflow_id: str, *, force: bool = False) -> dict:
    wf = await db.get_workflow(workflow_id)
    if not wf:
        raise WorkflowAdminError(f"workflow not found: {workflow_id}", 404)

    steps = await db.get_workflow_steps(workflow_id)
    if any(s["status"] == "processing" for s in steps) and not force:
        raise WorkflowAdminError(
            "workflow has processing steps; wait or use force=true", 409
        )

    file_ids = await _collect_workflow_file_ids(workflow_id)
    await db.delete_workflow_record(workflow_id)

    removed: list[str] = []
    for fid in file_ids:
        if await db.file_is_orphan(fid):
            await db.delete_file_record(fid)
            try:
                await storage.delete(fid)
            except FileNotFoundError:
                pass
            removed.append(fid)

    return {
        "workflow_id": workflow_id,
        "deleted": True,
        "files_removed": removed,
    }


async def delete_workflows_batch(
    workflow_ids: list[str], *, force: bool = False
) -> dict:
    deleted: list[str] = []
    errors: list[dict] = []

    for wid in workflow_ids:
        try:
            await delete_workflow(wid, force=force)
            deleted.append(wid)
        except WorkflowAdminError as e:
            errors.append({"workflow_id": wid, "error": e.message, "code": e.status_code})

    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "errors": errors,
        "error_count": len(errors),
    }


async def build_workflows_zip(workflow_ids: list[str]) -> tuple[bytes, str]:
    if not workflow_ids:
        raise WorkflowAdminError("workflow_ids required", 422)

    buf = io.BytesIO()
    added = 0
    seen_arc: set[str] = set()
    multi = len(workflow_ids) > 1
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for wid in workflow_ids:
            wf = await db.get_workflow(wid)
            if not wf:
                continue
            entry = await db.get_file(wf["entry_file_id"])
            prefix: str | None = None
            if multi:
                if entry:
                    prefix = Path(entry["original_name"]).stem
                else:
                    prefix = wid[:8]

            if entry:
                try:
                    path = await storage.get_path(wf["entry_file_id"])
                    arc = flat_arc_name(
                        entry["original_name"], seen_arc, prefix=prefix
                    )
                    zf.write(path, arc)
                    added += 1
                except FileNotFoundError:
                    pass

            for step in await db.get_workflow_steps(wid):
                if step["status"] != "completed" or not step.get("output_file_id"):
                    continue
                out = await db.get_file(step["output_file_id"])
                if not out:
                    continue
                try:
                    path = await storage.get_path(step["output_file_id"])
                    arc = flat_arc_name(
                        out["original_name"], seen_arc, prefix=prefix
                    )
                    zf.write(path, arc)
                    added += 1
                except FileNotFoundError:
                    pass

    if added == 0:
        raise WorkflowAdminError("no exportable files in selected workflows", 404)

    buf.seek(0)
    name = f"media-studio-export-{len(workflow_ids)}-tasks.zip"
    return buf.getvalue(), name
