# -*- coding: utf-8 -*-
"""Configuration API endpoints."""

from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_monitor_config, update_config

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    interval: int = 5
    enabled_metrics: Dict[str, bool] = {}
    retention_days: int = 7
    disk_partitions: list = []


@router.get("")
async def get_config():
    """Get current configuration."""
    return get_monitor_config()


@router.put("")
async def put_config(request: ConfigUpdateRequest):
    """Update configuration."""
    config = request.dict(exclude_unset=True)
    updated = update_config(config)
    return updated
