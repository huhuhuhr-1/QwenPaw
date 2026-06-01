from __future__ import annotations

import torch

from app.services.transcribe.backends.base import TranscribeBackend
from app.services.transcribe.local_models import resolve_configured_model_path


class LocalWhisperBackend(TranscribeBackend):
    def __init__(
        self,
        *,
        profile: str,
        model_path: str,
        device: str,
        compute_type: str,
    ):
        self.profile = profile
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None
        self._call_count = 0

    @property
    def name(self) -> str:
        return f"local-whisper/{self.profile}"

    def load(self) -> None:
        if self._model is not None:
            return

        from faster_whisper import WhisperModel

        resolved = resolve_configured_model_path(self.model_path)
        if resolved is None:
            raise FileNotFoundError(
                f"未在 models/ 中找到模型：{self.model_path}。"
                f"请先执行：uv run python scripts/download_whisper_model.py <模型名>"
            )

        self._model = WhisperModel(
            str(resolved),
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        if not self._model:
            self.load()
        segments, _info = self._model.transcribe(audio_path, language=language)
        text = "".join(s.text for s in segments)

        self._call_count += 1
        if self._call_count % 5 == 0 and self.device == "cuda":
            torch.cuda.empty_cache()

        return text.strip()

    def unload(self) -> None:
        self._model = None
        if self.device == "cuda":
            torch.cuda.empty_cache()
        import gc

        gc.collect()
