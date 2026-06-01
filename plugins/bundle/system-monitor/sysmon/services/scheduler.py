# -*- coding: utf-8 -*-
"""Metrics collection scheduler."""

import asyncio
import logging
from datetime import datetime

from sysmon.db.sqlite import get_db, insert_metric, insert_process_snapshot
from sysmon.services.collector_cpu import collect_cpu_metrics
from sysmon.services.collector_memory import collect_memory_metrics
from sysmon.services.collector_disk import collect_disk_metrics
from sysmon.services.collector_handle import collect_handle_metrics
from sysmon.services.collector_process import collect_top_processes
from sysmon.config import get_interval, get_retention_days, is_metric_enabled

logger = logging.getLogger(__name__)

_collection_task: asyncio.Task | None = None
_running = False


async def _collect_once():
    """Run one collection cycle."""
    try:
        conn = get_db()

        all_records = []

        if is_metric_enabled("cpu"):
            all_records.extend(collect_cpu_metrics())

        if is_metric_enabled("memory"):
            all_records.extend(collect_memory_metrics())

        if is_metric_enabled("disk"):
            all_records.extend(collect_disk_metrics())

        if is_metric_enabled("handle"):
            all_records.extend(collect_handle_metrics())

        for record in all_records:
            insert_metric(conn, record.metric_type, record.name, record.value, record.unit)

        if is_metric_enabled("process"):
            top_procs = collect_top_processes(limit=20)
            for proc in top_procs:
                insert_process_snapshot(conn, proc.pid, proc.name, proc.cpu_percent, proc.memory_percent, proc.num_fds)

        conn.commit()
        conn.close()

        logger.debug("Collection cycle completed at %s", datetime.now())
    except Exception as e:
        logger.exception("Error in collection cycle: %s", e)


async def _collection_loop():
    """Continuously collect metrics at the configured interval."""
    global _running
    interval = get_interval()
    logger.info("Collection loop started with interval=%d seconds", interval)

    while _running:
        await _collect_once()
        await asyncio.sleep(interval)


def start_scheduler():
    """Start the metrics collection scheduler."""
    global _collection_task, _running
    if _running:
        logger.warning("Scheduler already running")
        return

    _running = True
    _collection_task = asyncio.create_task(_collection_loop())
    logger.info("Scheduler started")


async def stop_scheduler():
    """Stop the metrics collection scheduler."""
    global _collection_task, _running
    _running = False
    if _collection_task:
        _collection_task.cancel()
        try:
            await _collection_task
        except asyncio.CancelledError:
            pass
        _collection_task = None
    logger.info("Scheduler stopped")
