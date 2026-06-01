from __future__ import annotations

import logging

from app.config import settings as _default_settings
from app.services.transcribe.backends.base import TranscribeBackend


def _settings():
    return _default_settings
from app.services.transcribe.lanes import TRANSCRIBE_LANES, normalize_transcribe_lane

logger = logging.getLogger(__name__)


class TranscribeRegistry:
    def __init__(self):
        self._backends: dict[str, TranscribeBackend] = {}

    def backend_for_lane(self, lane: str) -> TranscribeBackend:
        from app.services.transcribe.lane_config import assert_lane_available

        lane = assert_lane_available(lane)
        if lane not in self._backends:
            self._backends[lane] = self._build_backend(lane)
        return self._backends[lane]

    def transcribe(self, lane: str, audio_path: str, language: str = "zh") -> str:
        backend = self.backend_for_lane(lane)
        return backend.transcribe(audio_path, language=language)

    def warmup(self, lanes: tuple[str, ...] | None = None) -> None:
        """Optional preload; failures are logged and do not propagate."""
        from app.services.transcribe.lane_config import available_lanes

        if lanes is None:
            targets = tuple(
                ln
                for ln in available_lanes()
                if self._lane_backend_kind(ln) == "local"
            )
        else:
            targets = lanes
        for lane in targets:
            try:
                backend = self.backend_for_lane(lane)
                if hasattr(backend, "load"):
                    logger.info("warming transcribe backend: %s", backend.name)
                    backend.load()
            except Exception as exc:
                logger.warning(
                    "transcribe warmup skipped for lane %s: %s", lane, exc
                )

    def unload_all(self) -> None:
        for backend in self._backends.values():
            backend.unload()
        self._backends.clear()

    def _lane_backend_kind(self, lane: str) -> str:
        cfg = _settings()
        lane = normalize_transcribe_lane(lane)
        if lane == "fast":
            return cfg.transcribe_fast_backend
        if lane == "slow":
            return cfg.transcribe_slow_backend
        return cfg.transcribe_external_backend

    def _build_backend(self, lane: str) -> TranscribeBackend:
        kind = self._lane_backend_kind(lane)
        if kind == "local":
            from app.services.transcribe.backends.local import LocalWhisperBackend

            return LocalWhisperBackend(
                profile=lane,
                model_path=self._local_model_path(lane),
                device=self._local_device(lane),
                compute_type=self._local_compute_type(lane),
            )
        if kind in ("openai", "dashscope"):
            return self._build_openai_backend(lane, kind)
        raise ValueError(f"unknown transcribe backend kind: {kind}")

    def _build_openai_backend(self, lane: str, kind: str) -> TranscribeBackend:
        from app.services.transcribe.backends.openai_compatible import OpenAICompatibleBackend

        cfg = _settings()
        if kind == "dashscope":
            api_key = cfg.dashscope_api_key or cfg.transcribe_openai_api_key
            base_url = cfg.dashscope_base_url
            model = cfg.dashscope_asr_model
            label = "dashscope"
        else:
            api_key = cfg.transcribe_openai_api_key
            base_url = cfg.transcribe_openai_base_url
            model = cfg.transcribe_openai_model
            label = "openai-compatible"
        return OpenAICompatibleBackend(
            profile=lane,
            api_key=api_key,
            base_url=base_url,
            model=model,
            provider_label=label,
        )


transcribe_registry = TranscribeRegistry()
