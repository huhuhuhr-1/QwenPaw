from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.shared.storage import db, storage

router = APIRouter()

_MEDIA_BY_SUFFIX = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".aac": "audio/aac",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
}


@router.get("/files/{file_id}")
async def get_file(file_id: str, download: bool = Query(False)):
    """Serve stored files for inline preview or download."""
    file_info = await db.get_file(file_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {file_id}")

    path = await storage.get_path(file_id)
    name = file_info["original_name"]
    suffix = Path(name).suffix.lower()
    media_type = _MEDIA_BY_SUFFIX.get(suffix, "application/octet-stream")
    disposition = "attachment" if download else "inline"

    return FileResponse(
        str(path),
        media_type=media_type,
        filename=name,
        headers={"Content-Disposition": f'{disposition}; filename="{name}"'},
    )
