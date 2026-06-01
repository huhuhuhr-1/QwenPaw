import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.shared.storage import db, storage
from app.services.media.audio import audio_service
from app.models.schemas import ToAudioRequest, TaskCreatedResponse

router = APIRouter()


@router.post("/to-audio", response_model=TaskCreatedResponse, status_code=202)
async def convert_to_audio(req: ToAudioRequest):
    file_info = await db.get_file(req.file_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {req.file_id}")
    if file_info["file_type"] != "video":
        raise HTTPException(422, f"expected video, got '{file_info['file_type']}'")

    input_path = await storage.get_path(req.file_id)

    out_id = uuid.uuid4().hex[:12]
    base = Path(file_info["original_name"]).stem
    out_name = f"{base}.{req.format}"
    from app.config import settings
    out_dir = Path(settings.data_dir) / "files" / out_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(out_dir / out_name)

    # Register output file immediately
    await db.create_file(out_id, "audio", out_name, output_path)

    # Run extraction in a task-like manner
    try:
        result = await audio_service.extract_audio(str(input_path), output_path, req.format, req.quality)
        file_size = Path(result).stat().st_size
        await db.update_file_size(out_id, file_size)
    except Exception as e:
        raise HTTPException(500, f"audio extraction failed: {e}")

    return TaskCreatedResponse(
        task_id=out_id,
        output_file_id=out_id,
        status="completed",
    )


@router.get("/audio/{file_id}")
async def download_audio(file_id: str):
    file_info = await db.get_file(file_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {file_id}")
    if file_info["file_type"] != "audio":
        raise HTTPException(422, f"expected audio, got '{file_info['file_type']}'")

    media_type = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
    }.get(Path(file_info["original_name"]).suffix, "application/octet-stream")

    path = await storage.get_path(file_id)
    return FileResponse(str(path), media_type=media_type,
                        filename=file_info["original_name"])
