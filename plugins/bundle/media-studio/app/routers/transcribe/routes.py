import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.services.shared.storage import db, storage
from app.services.transcribe.service import transcribe_service
from app.models.schemas import ToDocumentRequest, TaskCreatedResponse

router = APIRouter()


@router.post("/to-document", response_model=TaskCreatedResponse, status_code=202)
async def to_document(req: ToDocumentRequest):
    file_info = await db.get_file(req.audio_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {req.audio_id}")
    if file_info["file_type"] != "audio":
        raise HTTPException(422, f"expected audio, got '{file_info['file_type']}'")

    input_path = await storage.get_path(req.audio_id)

    out_id = uuid.uuid4().hex[:12]
    base = Path(file_info["original_name"]).stem
    out_name = f"{base}.txt"
    out_dir = Path(settings.data_dir) / "files" / out_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(out_dir / out_name)

    await db.create_file(out_id, "markdown", out_name, output_path)

    try:
        text = transcribe_service.transcribe(str(input_path), language=req.language)
        Path(output_path).write_text(text, encoding="utf-8")
        file_size = Path(output_path).stat().st_size
        await db.update_file_size(out_id, file_size)
    except Exception as e:
        raise HTTPException(500, f"transcription failed: {e}")

    return TaskCreatedResponse(
        task_id=out_id,
        output_file_id=out_id,
        status="completed",
    )


@router.get("/document/{file_id}")
async def download_document(file_id: str):
    file_info = await db.get_file(file_id)
    if not file_info:
        raise HTTPException(404, f"file not found: {file_id}")
    if file_info["file_type"] not in ("markdown",):
        raise HTTPException(422, f"expected document, got '{file_info['file_type']}'")

    path = await storage.get_path(file_id)
    return FileResponse(str(path), media_type="text/plain; charset=utf-8",
                        filename=file_info["original_name"])
