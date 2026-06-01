"""运行时配置 — 读 DB 覆盖 env,cache 60s。"""

import json
import time
from typing import Any, Dict, List, Optional

from app.config import settings as env_settings
from app.database import get_setting, set_setting, list_settings

_CACHE_TTL_SEC = 60
_cache: Optional[Dict[str, Any]] = None
_cache_ts: float = 0


def _parse_languages_json(raw: str) -> List[str]:
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v]
    except (json.JSONDecodeError, TypeError):
        pass
    return env_settings.collect_languages


def _coerce(key: str, raw: str) -> Any:
    """按 key 类型转换字符串 → 原始类型。"""
    if key == "collect_enabled":
        return raw.lower() in ("true", "1", "yes")
    if key == "collect_interval_min":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 60
    if key == "collect_period":
        return raw if raw in ("daily", "weekly", "monthly") else "daily"
    if key == "collect_languages":
        return _parse_languages_json(raw)
    return raw


async def get_runtime_settings() -> Dict[str, Any]:
    """读 DB 配置,fallback env settings。Cache 60s。"""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL_SEC:
        return _cache

    db_values = await list_settings()
    cfg = {
        "collect_enabled": env_settings.collect_enabled,
        "collect_interval_min": env_settings.collect_interval_min,
        "collect_period": env_settings.collect_period,
        "collect_languages": list(env_settings.collect_languages),
    }
    for key, raw in db_values.items():
        if key in cfg:
            cfg[key] = _coerce(key, raw)

    _cache = cfg
    _cache_ts = now
    return cfg


async def set_runtime_setting(key: str, value: Any) -> None:
    """写一个 setting 到 DB + 清缓存。"""
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    await set_setting(key, raw)
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0


def clear_cache() -> None:
    """手工清 cache(给 collector 用)。"""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0
