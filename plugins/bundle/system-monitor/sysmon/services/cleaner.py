# -*- coding: utf-8 -*-
"""Data cleanup service."""

import logging
from datetime import datetime, timedelta

from sysmon.db.sqlite import cleanup_data
from sysmon.config import get_retention_days

logger = logging.getLogger(__name__)


def cleanup_old_data() -> dict:
    """Clean up metrics older than retention period. Returns cleanup stats."""
    try:
        retention_days = get_retention_days()
        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()

        metrics_deleted, processes_deleted = cleanup_data(cutoff_str)

        logger.info("Cleanup completed: metrics=%d, processes=%d deleted before %s",
                   metrics_deleted, processes_deleted, cutoff_str)

        return {
            "metrics_deleted": metrics_deleted,
            "processes_deleted": processes_deleted,
            "cutoff": cutoff_str,
        }
    except Exception as e:
        logger.exception("Cleanup failed: %s", e)
        return {"error": str(e)}


def get_stats() -> dict:
    """Get data statistics."""
    try:
        from sysmon.db.sqlite import get_data_stats
        return get_data_stats()
    except Exception as e:
        logger.exception("Failed to get stats: %s", e)
        return {"error": str(e)}
