# -*- coding: utf-8 -*-
"""Metrics API router."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sysmon.db.sqlite import query_metrics, query_process_top, get_data_stats
from sysmon.services.collector_cpu import collect_cpu_metrics
from sysmon.services.collector_memory import collect_memory_metrics
from sysmon.services.collector_disk import collect_disk_metrics
from sysmon.services.collector_handle import collect_handle_metrics
from sysmon.services.cleaner import cleanup_old_data, get_stats

router = APIRouter()


class CurrentMetricsResponse(BaseModel):
    cpu: dict
    memory: dict
    disk: list
    handles: dict
    load: dict


@router.get("/current", response_model=CurrentMetricsResponse)
async def get_current_metrics():
    """Get current system metrics (real-time collection)."""
    cpu_records = collect_cpu_metrics()
    memory_records = collect_memory_metrics()
    disk_records = collect_disk_metrics()
    handle_records = collect_handle_metrics()

    # Parse CPU
    cpu_percent = 0.0
    cpu_count = 0
    load = [0.0, 0.0, 0.0]
    for r in cpu_records:
        if r.name == "cpu_percent":
            cpu_percent = r.value
        elif r.name == "cpu_count":
            cpu_count = int(r.value)
        elif r.name in ("load_1min", "load_5min", "load_15min"):
            idx = {"load_1min": 0, "load_5min": 1, "load_15min": 2}[r.name]
            load[idx] = r.value

    # Parse Memory
    memory_percent = 0.0
    memory_used = 0.0
    memory_total = 0.0
    for r in memory_records:
        if r.name == "memory_percent":
            memory_percent = r.value
        elif r.name == "memory_used":
            memory_used = r.value / (1024**3)  # bytes to GB
        elif r.name == "memory_total":
            memory_total = r.value / (1024**3)

    # Parse Disk
    disk_info = []
    for r in disk_records:
        if r.name.endswith("_percent") and r.name.startswith("disk_"):
            mount = r.name.replace("disk_", "").replace("_percent", "").replace("_", "/")
            disk_info.append({
                "mount": mount,
                "percent": r.value,
            })

    # Parse Handles
    handle_total = 0
    process_count = 0
    for r in handle_records:
        if r.name == "num_open_files":
            handle_total = r.value
        elif r.name == "num_processes":
            process_count = r.value

    return CurrentMetricsResponse(
        cpu={"percent": cpu_percent, "cores": cpu_count, "load": load},
        memory={"total": round(memory_total, 2), "used": round(memory_used, 2), "percent": memory_percent},
        disk=disk_info,
        handles={"total": int(handle_total), "processes": int(process_count)},
        load={"1min": load[0], "5min": load[1], "15min": load[2]},
    )


@router.get("/trend/{metric_type}")
async def get_trend(
    metric_type: str,
    start: Optional[str] = Query(None, description="Start time ISO format"),
    end: Optional[str] = Query(None, description="End time ISO format"),
    limit: int = Query(500, ge=1, le=5000),
):
    """Get metric trend data."""
    data = query_metrics(metric_type, start, end, limit)
    return {
        "metric_type": metric_type,
        "start": start,
        "end": end,
        "count": len(data),
        "data": data,
    }


@router.get("/top/{metric_type}")
async def get_top(metric_type: str, limit: int = Query(20, ge=1, le=100)):
    """Get Top N realtime ranking (current moment)."""
    if metric_type not in ("cpu", "memory", "handle"):
        metric_type = "cpu"

    data = query_process_top(metric_type, None, None, limit)
    return {
        "type": metric_type,
        "data": data,
    }


@router.get("/process/top")
async def get_process_top(
    type: str = Query("cpu", description="cpu/memory/handle"),
    start: Optional[str] = Query(None, description="Start time"),
    end: Optional[str] = Query(None, description="End time"),
    limit: int = Query(20, ge=1, le=100),
):
    """Process Top N with time range filter."""
    data = query_process_top(type, start, end, limit)
    return {
        "type": type,
        "start": start or (datetime.now() - timedelta(hours=1)).isoformat(),
        "end": end or datetime.now().isoformat(),
        "data": data,
    }


@router.get("/services")
async def get_services():
    """Service summary status."""
    cpu_records = collect_cpu_metrics()
    memory_records = collect_memory_metrics()
    handle_records = collect_handle_metrics()

    cpu_percent = 0.0
    load = [0.0, 0.0, 0.0]
    for r in cpu_records:
        if r.name == "cpu_percent":
            cpu_percent = r.value
        elif r.name in ("load_1min", "load_5min", "load_15min"):
            idx = {"load_1min": 0, "load_5min": 1, "load_15min": 2}[r.name]
            load[idx] = r.value

    memory_percent = 0.0
    memory_used = 0.0
    for r in memory_records:
        if r.name == "memory_percent":
            memory_percent = r.value
        elif r.name == "memory_used":
            memory_used = r.value / (1024**3)

    handle_total = 0
    for r in handle_records:
        if r.name == "num_open_files":
            handle_total = r.value

    return {
        "cpu": {"percent": cpu_percent, "load": load},
        "memory": {"percent": memory_percent, "used_gb": round(memory_used, 2)},
        "handles": {"total": int(handle_total)},
    }


class CleanupRequest(BaseModel):
    before: Optional[str] = None


@router.post("/cleanup")
async def cleanup(request: CleanupRequest):
    """Manual data cleanup."""
    if request.before:
        from sysmon.db.sqlite import cleanup_data
        metrics_deleted, processes_deleted = cleanup_data(request.before)
        return {"metrics_deleted": metrics_deleted, "processes_deleted": processes_deleted, "before": request.before}
    else:
        result = cleanup_old_data()
        stats = get_stats()
        return {**result, "remaining_stats": stats}


@router.get("/stats")
async def stats():
    """Get data statistics."""
    return get_stats()
