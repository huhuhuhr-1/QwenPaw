# -*- coding: utf-8 -*-
"""Process-level metrics collector."""

import psutil
from datetime import datetime
from typing import List

from app.db.models import ProcessSnapshot


def collect_top_processes(limit: int = 10, sort_by: str = "cpu") -> List[ProcessSnapshot]:
    """Collect top N processes by CPU or memory usage."""
    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_fds']):
        try:
            info = proc.info
            # CPU percent needs interval to be accurate
            cpu = proc.cpu_percent(interval=0.1)
            mem = info.get('memory_percent', 0)
            num_fds = info.get('num_fds', 0)

            processes.append(ProcessSnapshot(
                pid=info['pid'],
                name=info['name'],
                cpu_percent=cpu,
                memory_percent=mem,
                num_fds=num_fds if num_fds else 0,
                timestamp=datetime.now(),
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort and limit
    if sort_by == "cpu":
        processes.sort(key=lambda p: p.cpu_percent, reverse=True)
    else:
        processes.sort(key=lambda p: p.memory_percent, reverse=True)

    return processes[:limit]
