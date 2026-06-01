"""设置路由 — runtime config + 手动触发采集。"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.collector import collect_once
from app.settings import get_runtime_settings, set_runtime_setting

logger = logging.getLogger(__name__)

router = APIRouter()

# 简单任务状态机:{task_id: {status, started_at, result?}}
_TRIGGER_TASKS: Dict[str, Dict[str, Any]] = {}
_TRIGGER_LOCK = asyncio.Lock()


def _cleanup_old_tasks() -> None:
    """Evict completed tasks older than 1 hour to bound memory. Keep all running tasks."""
    if len(_TRIGGER_TASKS) <= 20:
        return
    cutoff = time.time() - 3600
    for tid in list(_TRIGGER_TASKS.keys()):
        info = _TRIGGER_TASKS[tid]
        if info.get("status") != "running" and info.get("started_at", 0) < cutoff:
            del _TRIGGER_TASKS[tid]


class SettingsUpdate(BaseModel):
    collect_enabled: Optional[bool] = None
    collect_interval_min: Optional[int] = Field(default=None, ge=1, le=10080)
    collect_period: Optional[str] = None
    collect_languages: Optional[List[str]] = None


@router.get("")
async def get_settings() -> Dict[str, Any]:
    """读当前 runtime 配置。"""
    return await get_runtime_settings()


@router.put("")
async def update_settings(payload: SettingsUpdate) -> Dict[str, str]:
    """局部更新 runtime 配置。"""
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    for key, value in updates.items():
        await set_runtime_setting(key, value)
    return {"ok": "true", "updated": ",".join(updates.keys())}


@router.post("/trigger-collect")
async def trigger_collect() -> Dict[str, str]:
    """手动触发一次采集。如有任务在跑返回 409。"""
    async with _TRIGGER_LOCK:
        for tid, info in _TRIGGER_TASKS.items():
            if info.get("status") == "running":
                raise HTTPException(
                    status_code=409, detail=f"collect already running: {tid}"
                )
        task_id = uuid.uuid4().hex[:12]
        _TRIGGER_TASKS[task_id] = {"status": "running", "started_at": time.time()}
        asyncio.create_task(_run_trigger(task_id))
    return {"task_id": task_id, "status": "running"}


@router.get("/trigger-collect/{task_id}")
async def get_trigger_status(task_id: str) -> Dict[str, Any]:
    """查手动采集任务状态。404 表示 task_id 不存在或已被清理。"""
    info = _TRIGGER_TASKS.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, **info}


async def _run_trigger(task_id: str) -> None:
    """后台跑 collect_once,超时 5 分钟。"""
    try:
        result = await asyncio.wait_for(collect_once(), timeout=300)
        _TRIGGER_TASKS[task_id]["status"] = "done"
        _TRIGGER_TASKS[task_id]["result"] = result
    except asyncio.TimeoutError:
        _TRIGGER_TASKS[task_id]["status"] = "timeout"
    except Exception as e:  # noqa: BLE001
        _TRIGGER_TASKS[task_id]["status"] = "error"
        _TRIGGER_TASKS[task_id]["error"] = f"{type(e).__name__}: {e}"
        logger.exception("Trigger collect failed: %s", e)
    finally:
        _cleanup_old_tasks()
