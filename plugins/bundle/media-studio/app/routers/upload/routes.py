import uuid
import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import settings
from app.services.shared.storage import db, storage
from app.models.schemas import UploadResponse, FileType

router = APIRouter()


SUPPORTED_EXTENSIONS = {
    "video": {".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv"},
    "audio": {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"},
    "markdown": {".md", ".txt", ".markdown"},
}


def detect_file_type(ext: str) -> FileType:
    ext = ext.lower()
    for ft, exts in SUPPORTED_EXTENSIONS.items():
        if ext in exts:
            return FileType(ft)
    raise HTTPException(422, f"unsupported file type '{ext}'")


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(422, "filename required")

    ext = Path(file.filename).suffix
    if not ext:
        raise HTTPException(422, "file must have an extension")

    file_type = detect_file_type(ext)
    content = await file.read()

    if not content:
        raise HTTPException(422, "empty file")

    file_id = uuid.uuid4().hex[:12]
    stored_path = await storage.save(file_id, file.filename, content)

    file_hash = hashlib.sha256(content).hexdigest()[:16]
    size = len(content)
    mime = file.content_type or ""

    await db.create_file(file_id, file_type.value, file.filename,
                         str(stored_path), size, mime, file_hash)

    return UploadResponse(
        file_id=file_id,
        file_type=file_type,
        original_name=file.filename,
        size_bytes=size,
    )
