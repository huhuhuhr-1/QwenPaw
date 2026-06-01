# -*- coding: utf-8 -*-
"""Disk metrics collector."""

import psutil
from datetime import datetime
from typing import List

from sysmon.db.models import MetricRecord


def collect_disk_metrics() -> List[MetricRecord]:
    """Collect disk metrics."""
    records = []
    now = datetime.now()

    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            records.append(MetricRecord(
                timestamp=now,
                metric_type="disk",
                name=f"disk_{partition.mountpoint.replace('/', '_')}_percent",
                value=usage.percent,
                unit="percent",
            ))
            records.append(MetricRecord(
                timestamp=now,
                metric_type="disk",
                name=f"disk_{partition.mountpoint.replace('/', '_')}_used",
                value=usage.used,
                unit="bytes",
            ))
            records.append(MetricRecord(
                timestamp=now,
                metric_type="disk",
                name=f"disk_{partition.mountpoint.replace('/', '_')}_total",
                value=usage.total,
                unit="bytes",
            ))
        except PermissionError:
            continue

    # Disk IO
    io = psutil.disk_io_counters()
    if io:
        records.append(MetricRecord(
            timestamp=now,
            metric_type="disk",
            name="disk_read_bytes",
            value=io.read_bytes,
            unit="bytes",
        ))
        records.append(MetricRecord(
            timestamp=now,
            metric_type="disk",
            name="disk_write_bytes",
            value=io.write_bytes,
            unit="bytes",
        ))

    return records
