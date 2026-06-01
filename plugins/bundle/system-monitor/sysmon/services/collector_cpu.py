# -*- coding: utf-8 -*-
"""CPU metrics collector."""

import psutil
from datetime import datetime
from typing import List

from sysmon.db.models import MetricRecord


def collect_cpu_metrics() -> List[MetricRecord]:
    """Collect CPU metrics."""
    records = []
    now = datetime.now()

    # Overall CPU percent
    cpu_percent = psutil.cpu_percent(interval=0.1)
    records.append(MetricRecord(
        timestamp=now,
        metric_type="cpu",
        name="cpu_percent",
        value=cpu_percent,
        unit="percent",
    ))

    # CPU count
    cpu_count = psutil.cpu_count()
    records.append(MetricRecord(
        timestamp=now,
        metric_type="cpu",
        name="cpu_count",
        value=float(cpu_count),
        unit="cores",
    ))

    # Load average (only on Linux)
    try:
        load_avg = psutil.getloadavg()
        records.append(MetricRecord(
            timestamp=now,
            metric_type="load",
            name="load_1min",
            value=load_avg[0],
            unit="float",
        ))
        records.append(MetricRecord(
            timestamp=now,
            metric_type="load",
            name="load_5min",
            value=load_avg[1],
            unit="float",
        ))
        records.append(MetricRecord(
            timestamp=now,
            metric_type="load",
            name="load_15min",
            value=load_avg[2],
            unit="float",
        ))
    except AttributeError:
        # getloadavg not available on Windows
        pass

    return records
