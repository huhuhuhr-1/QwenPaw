# -*- coding: utf-8 -*-
"""System Monitor Database Models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MetricRecord(BaseModel):
    """A single metric data point."""
    id: Optional[int] = None
    timestamp: datetime
    metric_type: str  # cpu, memory, disk, handle, process
    name: str
    value: float
    unit: str


class ProcessSnapshot(BaseModel):
    """Process-level metrics snapshot."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    num_fds: int
    timestamp: datetime


class ConfigItem(BaseModel):
    """Configuration item."""
    key: str
    value: str
    description: Optional[str] = None
