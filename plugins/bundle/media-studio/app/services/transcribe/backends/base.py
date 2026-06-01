from __future__ import annotations

from abc import ABC, abstractmethod


class TranscribeBackend(ABC):
    """Pluggable speech-to-text backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        ...

    def load(self) -> None:
        """Optional warmup (local models)."""

    def unload(self) -> None:
        """Optional teardown."""
