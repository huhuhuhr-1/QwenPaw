# -*- coding: utf-8 -*-
"""Memory metrics collector."""

import psutil
from datetime import datetime
from typing import List

from sysmon.db.models import MetricRecord


def collect_memory_metrics() -> List[MetricRecord]:
    """Collect memory metrics."""
    records = []
    now = datetime.now()

    mem = psutil.virtual_memory()

    records.append(MetricRecord(
        timestamp=now,
        metric_type="memory",
        name="memory_percent",
        value=mem.percent,
        unit="percent",
    ))
    records.append(MetricRecord(
        timestamp=now,
        metric_type="memory",
        name="memory_used",
        value=mem.used,
        unit="bytes",
    ))
    records.append(MetricRecord(
        timestamp=now,
        metric_type="memory",
        name="memory_available",
        value=mem.available,
        unit="bytes",
    ))
    records.append(MetricRecord(
        timestamp=now,
        metric_type="memory",
        name="memory_total",
        value=mem.total,
        unit="bytes",
    ))

    # Swap
    swap = psutil.swap_memory()
    records.append(MetricRecord(
        timestamp=now,
        metric_type="memory",
        name="swap_percent",
        value=swap.percent,
        unit="percent",
    ))

    return records
