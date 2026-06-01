"""OpenAI-compatible audio transcription API (/v1/audio/transcriptions).

Works with OpenAI Whisper, Alibaba DashScope compatible mode, and other providers.
"""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.services.transcribe.backends.base import TranscribeBackend


class OpenAICompatibleBackend(TranscribeBackend):
    def __init__(
        self,
        *,
        profile: str,
        api_key: str,
        base_url: str,
        model: str,
        provider_label: str = "openai-compatible",
    ):
        if not api_key:
            raise RuntimeError(
                f"API key required for transcribe backend {provider_label} ({profile})"
            )
        self.profile = profile
        self.model = model
        self._provider_label = provider_label
        self._client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))

    @property
    def name(self) -> str:
        return f"{self._provider_label}/{self.profile}"

    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        path = Path(audio_path)
        with path.open("rb") as audio_file:
            result = self._client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
            )
        text = getattr(result, "text", None) or str(result)
        return text.strip()
