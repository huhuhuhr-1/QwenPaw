"""Transcribe facade — delegates to lane-specific backends via registry."""

from app.services.transcribe.backends.registry import transcribe_registry


class TranscribeService:
    def load_model(self) -> None:
        """Best-effort preload after config change; never required for startup."""
        transcribe_registry.warmup()

    def transcribe(self, audio_path: str, language: str = "zh", *, lane: str = "slow") -> str:
        return transcribe_registry.transcribe(lane, audio_path, language=language)

    def unload(self) -> None:
        transcribe_registry.unload_all()


transcribe_service = TranscribeService()
