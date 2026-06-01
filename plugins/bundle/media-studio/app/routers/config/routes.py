from fastapi import APIRouter, HTTPException

import app.config as config_module
from app.models.schemas import (
    ProcessorConfigResponse,
    ProcessorConfigUpdate,
    TranscribeLaneStatus,
)
from app.services.config.runtime import get_public_config, reload_settings, write_env_updates
from app.services.transcribe.lane_config import available_lanes, lane_configuration
from app.services.transcribe.local_models import is_valid_local_model_path

router = APIRouter(prefix="/config", tags=["config"])


def _build_response() -> ProcessorConfigResponse:
    raw = get_public_config(config_module.settings)
    raw["transcribe_lanes"] = [TranscribeLaneStatus(**row) for row in raw["transcribe_lanes"]]
    return ProcessorConfigResponse(**raw)


@router.get("", response_model=ProcessorConfigResponse)
async def get_processor_config():
    return _build_response()


@router.put("", response_model=ProcessorConfigResponse)
async def update_processor_config(body: ProcessorConfigUpdate):
    updates: dict = {}
    data = body.model_dump(exclude_none=True)

    for key, val in data.items():
        if key == "transcribe_default_lane" and val is not None:
            updates["transcribe_default_lane"] = val.value if hasattr(val, "value") else val
        else:
            updates[key] = val

    if not updates:
        raise HTTPException(422, "no fields to update")

    s = config_module.settings
    fast_local = updates.get("transcribe_fast_backend", s.transcribe_fast_backend) == "local"
    slow_local = updates.get("transcribe_slow_backend", s.transcribe_slow_backend) == "local"
    fast_on = updates.get("transcribe_fast_enabled", s.transcribe_fast_enabled)
    slow_on = updates.get("transcribe_slow_enabled", s.transcribe_slow_enabled)
    if fast_on and fast_local and "transcribe_fast_model_path" in updates:
        path = updates["transcribe_fast_model_path"]
        if not is_valid_local_model_path(path):
            raise HTTPException(422, f"快队列模型未在 models/ 中就绪: {path}")
    if slow_on and slow_local and "transcribe_slow_model_path" in updates:
        path = updates["transcribe_slow_model_path"]
        if not is_valid_local_model_path(path):
            raise HTTPException(422, f"慢队列模型未在 models/ 中就绪: {path}")

    write_env_updates(updates)
    reload_settings()

    # 关闭队列后默认 lane 可能不可用：自动落到第一个可用队列，避免保存失败
    avail = available_lanes()
    default = config_module.settings.transcribe_default_lane
    if default not in avail:
        if avail:
            write_env_updates({"transcribe_default_lane": avail[0]})
            reload_settings()
        elif "transcribe_default_lane" in updates:
            raise HTTPException(
                422,
                "没有可用的转写队列：请至少启用并配置一个队列，或不要关闭全部队列。",
            )

    return _build_response()


@router.get("/transcribe-lanes")
async def list_transcribe_lanes():
    """Available lanes for upload UI (only routable lanes)."""
    from app.services.transcribe.lane_config import all_lane_configurations, available_lanes

    return {
        "default_lane": config_module.settings.transcribe_default_lane,
        "available_lanes": available_lanes(),
        "lanes": all_lane_configurations(),
    }
