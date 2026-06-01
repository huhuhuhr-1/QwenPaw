from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class FileType(str, Enum):
    video = "video"
    audio = "audio"
    markdown = "markdown"


class StepType(str, Enum):
    extract_audio = "extract_audio"
    transcribe = "transcribe"
    polish = "polish"


class StepStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    paused = "paused"
    completed = "completed"
    failed = "failed"


# --- Requests ---

class UploadResponse(BaseModel):
    file_id: str
    file_type: FileType
    original_name: str
    size_bytes: int


class ToAudioRequest(BaseModel):
    file_id: str
    format: str = "mp3"
    quality: int = Field(default=4, ge=0, le=9)


class ToDocumentRequest(BaseModel):
    audio_id: str
    language: str = "zh"


class PolishRequest(BaseModel):
    file_id: str
    prompt: Optional[str] = None


class TranscribeLane(str, Enum):
    fast = "fast"
    slow = "slow"
    external = "external"


class CreateWorkflowRequest(BaseModel):
    file_id: str
    name: Optional[str] = None


class StepResponse(BaseModel):
    id: str
    step_type: StepType
    status: StepStatus
    input_file_id: Optional[str] = None  # video DAG: filled when upstream completes
    output_file_id: Optional[str] = None
    depends_on: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: Optional[str] = None
    entry_file_id: str
    entry_type: FileType
    entry_file_name: str
    status: WorkflowStatus
    transcribe_lane: Optional[str] = None
    steps: list[StepResponse] = []
    created_at: str


class WorkflowListItem(BaseModel):
    workflow_id: str
    name: Optional[str] = None
    entry_type: FileType
    entry_file_name: str
    status: WorkflowStatus
    transcribe_lane: Optional[str] = None
    step_count: int
    completed_count: int
    created_at: str


class WorkflowListResponse(BaseModel):
    items: list[WorkflowListItem]
    total: int
    page: int
    page_size: int


class WorkflowResultFile(BaseModel):
    file_id: str
    step_type: StepType
    name: str
    size_bytes: int
    download_url: str


class WorkflowResultsResponse(BaseModel):
    workflow_id: str
    files: list[WorkflowResultFile]


class TaskCreatedResponse(BaseModel):
    task_id: str
    output_file_id: str
    status: str = "pending"


class StepActionResponse(BaseModel):
    step_id: str
    status: str
    affected_count: int


class BatchWorkflowIdsRequest(BaseModel):
    workflow_ids: list[str] = Field(min_length=1)


class WorkflowDeleteResult(BaseModel):
    workflow_id: str
    deleted: bool
    files_removed: list[str] = []


class BatchDeleteResponse(BaseModel):
    deleted: list[str]
    deleted_count: int
    errors: list[dict] = []
    error_count: int = 0


class QueueLaneStats(BaseModel):
    running: int = 0
    queued: int = 0
    waiting_deps: int = 0
    completed: int = 0
    failed: int = 0
    buffer: int = 0
    capacity: int = 0
    enabled: bool = True
    available: bool = True


class GlobalQueueStatsResponse(BaseModel):
    updated_at: str
    queues: dict[str, QueueLaneStats]
    labels: dict[str, str] = {}
    control: dict = {}


class GlobalLogItem(BaseModel):
    id: str
    step_id: Optional[str] = None
    level: str
    message: str
    created_at: str
    step_type: Optional[str] = None
    workflow_id: Optional[str] = None
    source_name: Optional[str] = None


class GlobalLogListResponse(BaseModel):
    items: list[GlobalLogItem]
    total: int
    page: int
    page_size: int


class QueueControlResponse(BaseModel):
    pause_all: bool
    lanes: dict[str, dict]


class WorkflowControlResponse(BaseModel):
    workflow_id: str
    status: str
    affected_steps: int = 0


class BatchWorkflowControlResponse(BaseModel):
    updated: list[str]
    errors: list[dict] = []


class TranscribeLaneStatus(BaseModel):
    lane: str
    label: str
    scheduler_lane: str
    enabled: bool
    backend: str
    configured: bool
    available: bool
    reason: str
    model_path: Optional[str] = None
    device: Optional[str] = None
    compute_type: Optional[str] = None
    api_key_set: Optional[bool] = None
    max_concurrent: int = 1
    openai_api_key_set: Optional[bool] = None
    openai_api_key_masked: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    dashscope_api_key_set: Optional[bool] = None
    dashscope_api_key_masked: Optional[str] = None
    dashscope_base_url: Optional[str] = None
    dashscope_model: Optional[str] = None


class LocalModelOption(BaseModel):
    value: str
    label: str


class ProcessorConfigResponse(BaseModel):
    minimax_api_key_set: bool
    minimax_api_key_masked: str = ""
    env_file: str = ""
    transcribe_default_lane: str = "fast"
    default_lane_available: bool = False
    available_transcribe_lanes: list[str] = []
    transcribe_lanes: list[TranscribeLaneStatus] = []
    transcribe_pool_size: int = 1
    available_local_models: list[LocalModelOption] = []
    config_reload_hint: str = ""


class ProcessorConfigUpdate(BaseModel):
    minimax_api_key: Optional[str] = None
    transcribe_default_lane: Optional[TranscribeLane] = None
    transcribe_fast_enabled: Optional[bool] = None
    transcribe_slow_enabled: Optional[bool] = None
    transcribe_external_enabled: Optional[bool] = None
    transcribe_fast_backend: Optional[str] = None
    transcribe_slow_backend: Optional[str] = None
    transcribe_external_backend: Optional[str] = None
    transcribe_fast_model_path: Optional[str] = None
    transcribe_fast_device: Optional[str] = None
    transcribe_slow_model_path: Optional[str] = None
    transcribe_slow_device: Optional[str] = None
    transcribe_openai_api_key: Optional[str] = None
    transcribe_openai_base_url: Optional[str] = None
    transcribe_openai_model: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    dashscope_base_url: Optional[str] = None
    dashscope_asr_model: Optional[str] = None
    max_concurrent_transcribe_fast: Optional[int] = None
    max_concurrent_transcribe_slow: Optional[int] = None
    max_concurrent_transcribe_external: Optional[int] = None


class ArtifactListItem(BaseModel):
    file_id: str
    name: str
    file_type: str
    size_bytes: int
    step_type: StepType
    step_label: str
    workflow_id: str
    source_name: str
    completed_at: Optional[str] = None
    run_model: Optional[str] = None
    duration_seconds: Optional[float] = None
    download_url: str


class ArtifactListResponse(BaseModel):
    items: list[ArtifactListItem]
    total: int
    page: int
    page_size: int


class BatchArtifactIdsRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1)
