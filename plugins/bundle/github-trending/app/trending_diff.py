"""trending 增量检测 — 对比两天 daily_trending,新增的写事件。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import get_daily_trending, upload_monitor_events

logger = logging.getLogger(__name__)

_SINK_REPO = "github-trending-trending-diff"


def find_new_entries(
    today_data: Optional[Dict[str, Any]],
    yesterday_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """对比两天 trending.items,返回只在 today 出现的 repo。"""
    if not today_data or not yesterday_data:
        return []
    today_names = {item["full_name"] for item in today_data.get("items", [])}
    yesterday_names = {item["full_name"] for item in yesterday_data.get("items", [])}
    new_names = today_names - yesterday_names
    return [item for item in today_data.get("items", []) if item["full_name"] in new_names]


async def detect_and_record(today: str, yesterday: str, language: str = "all") -> int:
    """对比 today vs yesterday,新增的写 monitor_events。返回新增数。"""
    today_data = await get_daily_trending(today, language)
    yesterday_data = await get_daily_trending(yesterday, language)
    new_entries = find_new_entries(today_data, yesterday_data)
    if not new_entries:
        return 0

    events = [
        {
            "type": "trending_new",
            "title": f"新进 Trending: {item['full_name']}",
            "body": item.get("description", ""),
            "url": item.get("url", ""),
            "version": "",
            "time": datetime.now().isoformat(),
        }
        for item in new_entries
    ]
    await upload_monitor_events(
        repo=_SINK_REPO,
        repo_info={"language": language, "description": "Trending diff sink"},
        events=events,
    )
    logger.info("Trending diff: %d new entries for %s/%s", len(new_entries), language, today)
    return len(new_entries)
