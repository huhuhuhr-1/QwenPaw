"""Artifact (step output) listing and batch download."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.services.shared.storage import db, storage
from app.services.shared.zip_flat import flat_arc_name
from app.services.workflow.admin import WorkflowAdminError

STEP_DOWNLOAD_PREFIX = {
    "extract_audio": "/audio/",
    "transcribe": "/document/",
    "polish": "/polished/",
}

STEP_LABELS = {
    "extract_audio": "抽音频",
    "transcribe": "转写",
    "polish": "精修",
}


def artifact_download_url(step_type: str, file_id: str) -> str:
    prefix = STEP_DOWNLOAD_PREFIX.get(step_type, "/files/")
    return f"{prefix}{file_id}"


async def build_artifacts_zip(file_ids: list[str]) -> tuple[bytes, str]:
    if not file_ids:
        raise WorkflowAdminError("file_ids required", 422)

    buf = io.BytesIO()
    added = 0
    seen_arc: set[str] = set()
    multi = len(file_ids) > 1

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in file_ids:
            row = await db.get_artifact_by_file_id(fid)
            if not row:
                continue
            try:
                path = await storage.get_path(fid)
            except FileNotFoundError:
                continue

            source = Path(row.get("source_name") or "source").stem
            name = row["original_name"]
            prefix = source if multi else None
            arc = flat_arc_name(name, seen_arc, prefix=prefix)
            zf.write(path, arc)
            added += 1

    if added == 0:
        raise WorkflowAdminError("no exportable files in selection", 404)

    data = buf.getvalue()
    name = f"artifacts-export-{added}-files.zip"
    return data, name
