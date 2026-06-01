# -*- coding: utf-8 -*-
"""System handle metrics collector."""

import psutil
from datetime import datetime
from typing import List

from sysmon.db.models import MetricRecord


def collect_handle_metrics() -> List[MetricRecord]:
    """Collect system handle/file descriptor metrics."""
    records = []
    now = datetime.now()

    # Total open file descriptors across all processes
    total_fds = 0
    for proc in psutil.process_iter(['num_fds']):
        try:
            total_fds += proc.info['num_fds'] or 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    records.append(MetricRecord(
        timestamp=now,
        metric_type="handle",
        name="total_fds",
        value=float(total_fds),
        unit="count",
    ))

    # Process count
    records.append(MetricRecord(
        timestamp=now,
        metric_type="handle",
        name="num_processes",
        value=float(len(psutil.pids())),
        unit="count",
    ))

    # Network connections
    try:
        num_connections = len(psutil.net_connections())
    except Exception:
        num_connections = 0

    records.append(MetricRecord(
        timestamp=now,
        metric_type="handle",
        name="num_connections",
        value=float(num_connections),
        unit="count",
    ))

    return records
