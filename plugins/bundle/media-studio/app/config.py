from pathlib import Path

from typing_extensions import Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_ROOT = Path.home() / ".cache" / "qwenpaw" / "models"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="MEDIA_STUDIO_",
        extra="ignore",
        populate_by_name=True,
    )
    # Server
    host: str = "0.0.0.0"
    port: int = 7899
    data_dir: str = str(PROJECT_ROOT / "data")
    log_level: str = "INFO"

    # Storage
    storage_backend: str = "local"  # local | minio

    # --- Transcribe: default lane for new workflows ---
    transcribe_default_lane: str = "fast"  # fast=GPU, slow=CPU, external=cloud

    # Lane switches (disabled lanes are not routed)
    transcribe_fast_enabled: bool = True
    transcribe_slow_enabled: bool = True
    transcribe_external_enabled: bool = False

    # Legacy local whisper (slow lane defaults)
    whisper_model: str = "large-v3"
    model_path: str = str(MODELS_ROOT / "whisper-large-v3")
    device: str = "cuda"
    compute_type: str = "int8_float16"

    # Per-lane backend: local | openai | dashscope
    transcribe_fast_backend: str = "local"
    transcribe_slow_backend: str = "local"
    transcribe_external_backend: str = "openai"

    # 快队列：GPU + 大模型（主路径，质量与速度）
    transcribe_fast_model_path: str = ""
    transcribe_fast_device: str = "cuda"
    transcribe_fast_compute_type: str = "int8_float16"

    # 慢队列：CPU + 小模型（须在 ~/.cache/qwenpaw/models/ 已下载）
    transcribe_slow_model_path: str = ""
    transcribe_slow_device: str = "cpu"
    transcribe_slow_compute_type: str = "int8"

    # OpenAI-compatible cloud ASR (OpenAI / proxies / generic)
    transcribe_openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENAI_API_KEY",
            "MEDIA_STUDIO_TRANSCRIBE_OPENAI_API_KEY",
        ),
    )
    transcribe_openai_base_url: str = "https://api.openai.com/v1"
    transcribe_openai_model: str = "whisper-1"

    # Alibaba DashScope (OpenAI-compatible mode for Paraformer / SenseVoice)
    dashscope_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "DASHSCOPE_API_KEY",
            "MEDIA_STUDIO_DASHSCOPE_API_KEY",
        ),
    )
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_asr_model: str = "paraformer-v2"

    # Per-step concurrency (FIFO workers per queue)
    max_concurrent_extract: int | None = None
    max_concurrent_transcribe_fast: int | None = None
    max_concurrent_transcribe_slow: int | None = None
    max_concurrent_transcribe_external: int | None = None
    max_concurrent_polish: int | None = None

    # Legacy transcribe concurrency → slow lane
    max_concurrent_transcribe: int | None = None
    max_concurrent_gpu: int = 1
    max_concurrent_io: int = 2

    @model_validator(mode="after")
    def _resolve_concurrency_and_paths(self) -> Self:
        io = self.max_concurrent_io
        gpu = self.max_concurrent_gpu

        if self.max_concurrent_extract is None:
            object.__setattr__(self, "max_concurrent_extract", io)
        if self.max_concurrent_polish is None:
            object.__setattr__(self, "max_concurrent_polish", io)

        slow_default = self.max_concurrent_transcribe
        if slow_default is None:
            slow_default = gpu
        if self.max_concurrent_transcribe_slow is None:
            object.__setattr__(self, "max_concurrent_transcribe_slow", slow_default)
        if self.max_concurrent_transcribe_fast is None:
            object.__setattr__(self, "max_concurrent_transcribe_fast", max(1, gpu))
        if self.max_concurrent_transcribe_external is None:
            object.__setattr__(self, "max_concurrent_transcribe_external", io)

        if not self.transcribe_fast_model_path:
            object.__setattr__(self, "transcribe_fast_model_path", self.model_path)

        from app.services.transcribe.local_models import (
            is_valid_local_model_path,
            scan_local_models,
        )

        slow = self.transcribe_slow_model_path
        if not slow or not is_valid_local_model_path(slow):
            models = scan_local_models()
            small = next(
                (m["value"] for m in models if "small" in m["label"].lower()),
                None,
            )
            fallback = small or (models[0]["value"] if models else slow or "")
            if fallback and is_valid_local_model_path(fallback):
                object.__setattr__(self, "transcribe_slow_model_path", fallback)

        return self

    # Timeouts (seconds)
    timeout_extract: int = 600
    timeout_transcribe: int = 1800
    timeout_transcribe_fast: int = 600
    timeout_transcribe_slow: int = 1800
    timeout_transcribe_external: int = 3600
    timeout_polish: int = 300

    # API keys
    minimax_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("MINIMAX_API_KEY", "MEDIA_STUDIO_MINIMAX_API_KEY"),
    )


settings = Settings()
