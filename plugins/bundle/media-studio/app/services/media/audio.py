import asyncio

from app.services.shared.storage import db


class ProcessingError(Exception):
    def __init__(self, message: str, step: str = ""):
        self.message = message
        self.step = step
        super().__init__(message)


class AudioService:
    async def extract_audio(self, video_path: str, output_path: str,
                            fmt: str = "mp3", quality: int = 4,
                            step_id: str | None = None) -> str:
        import os
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if fmt == "mp3":
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
                   "-q:a", str(quality), output_path, "-y"]
        elif fmt == "m4a" or fmt == "aac":
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-c:a", "aac",
                   "-b:a", "128k", output_path, "-y"]
        elif fmt == "flac":
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-c:a", "flac", output_path, "-y"]
        elif fmt == "opus":
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-c:a", "libopus",
                   "-b:a", "64k", output_path, "-y"]
        else:
            cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
                   "-q:a", str(quality), output_path, "-y"]

        await db.add_log(step_id, "INFO", f"ffmpeg: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        except asyncio.TimeoutError:
            proc.kill()
            raise ProcessingError("ffmpeg timed out after 600s", step="extract_audio")

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[-500:]
            raise ProcessingError(f"ffmpeg failed: {err}", step="extract_audio")

        size = os.path.getsize(output_path)
        await db.add_log(step_id, "INFO", f"ffmpeg done: {output_path}, size={size}")
        return output_path


audio_service = AudioService()
