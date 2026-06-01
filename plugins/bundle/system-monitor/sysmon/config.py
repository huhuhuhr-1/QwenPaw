# -*- coding: utf-8 -*-
"""Configuration management for System Monitor."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_config: Dict[str, Any] = {}

DEFAULT_CONFIG = {
    "interval": 5,
    "enabled_metrics": {
        "cpu": True,
        "memory": True,
        "disk": True,
        "handle": True,
        "load": True,
        "process": True,
    },
    "retention_days": 7,
    "disk_partitions": [],
}


def load_config() -> Dict[str, Any]:
    """Load config from database (called at startup)."""
    global _config
    try:
        from sysmon.db.sqlite import get_config_value, set_config_value
        stored = get_config_value("monitor_config")
        if stored:
            _config = json.loads(stored)
        else:
            _config = DEFAULT_CONFIG.copy()
            save_config()
    except Exception as e:
        logger.warning("Failed to load config from DB, using defaults: %s", e)
        _config = DEFAULT_CONFIG.copy()

    logger.info("Config loaded: interval=%s, retention_days=%s",
                _config.get("interval"), _config.get("retention_days"))
    return _config


def get_monitor_config() -> Dict[str, Any]:
    """Get current config (in-memory)."""
    return _config.copy()


def update_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Update config and persist to database."""
    global _config
    _config.update(new_config)
    save_config()
    return _config.copy()


def save_config() -> None:
    """Persist current config to database."""
    try:
        from sysmon.db.sqlite import set_config_value
        set_config_value("monitor_config", json.dumps(_config, ensure_ascii=False))
    except Exception as e:
        logger.error("Failed to save config: %s", e)


def get_interval() -> int:
    """Get collection interval in seconds."""
    return _config.get("interval", 5)


def get_retention_days() -> int:
    """Get data retention period in days."""
    return _config.get("retention_days", 7)


def is_metric_enabled(metric: str) -> bool:
    """Check if a metric type is enabled."""
    return _config.get("enabled_metrics", {}).get(metric, True)
