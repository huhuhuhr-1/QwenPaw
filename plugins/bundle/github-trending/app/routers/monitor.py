"""监控路由"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import (
    get_subscriptions, add_subscription, delete_subscription, update_subscription,
    upload_monitor_events, get_monitor_events, list_watch_logs_by_subscription,
)
from app.monitor_refresh import refresh_one_repo

router = APIRouter()


# ── 订阅管理 ──


class SubscriptionResponse(BaseModel):
    id: int
    target: str
    enabled: bool
    notify_enabled: bool


@router.get("/subscriptions")
async def list_subscriptions() -> List[Dict]:
    """获取订阅列表(附 watch_log 信息)"""
    subs = await get_subscriptions()
    for sub in subs:
        logs = await list_watch_logs_by_subscription(sub["id"])
        if logs:
            sub["last_checked_at"] = logs[0].get("last_checked_at")
            sub["current_stars"] = logs[0].get("stars", 0)
            sub["current_forks"] = logs[0].get("forks", 0)
        else:
            sub["last_checked_at"] = None
            sub["current_stars"] = None
            sub["current_forks"] = None
    return subs


@router.post("/subscriptions")
async def create_subscription(target: str) -> Dict:
    """添加订阅,触发立即拉一次详情"""
    result = await add_subscription(target)
    # 触发一次立即刷新(不阻塞响应)
    sub_id = result["id"]
    asyncio.create_task(_initial_refresh(sub_id, target))
    return result


@router.delete("/subscriptions/{subscription_id}")
async def remove_subscription(subscription_id: int) -> Dict:
    """删除订阅"""
    await delete_subscription(subscription_id)
    return {"ok": True}


@router.put("/subscriptions/{subscription_id}")
async def edit_subscription(
    subscription_id: int,
    enabled: Optional[bool] = None,
    notify_enabled: Optional[bool] = None
) -> Dict:
    """更新订阅"""
    await update_subscription(subscription_id, enabled, notify_enabled)
    return {"ok": True}


# ── 监控动态 ──


class RepoInfo(BaseModel):
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: Optional[str] = None
    description: Optional[str] = None
    last_commit: Optional[str] = None


class MonitorEvent(BaseModel):
    type: str  # release, commit, star_update, issue
    title: str
    body: Optional[str] = None
    url: Optional[str] = None
    version: Optional[str] = None
    time: str


class MonitorUploadRequest(BaseModel):
    repo: str
    repo_info: RepoInfo
    events: List[MonitorEvent]


@router.post("/upload")
async def upload_events(data: MonitorUploadRequest) -> Dict:
    """上传监控数据"""
    events = [event.model_dump() for event in data.events]
    return await upload_monitor_events(data.repo, data.repo_info.model_dump(), events)


@router.get("/events")
async def list_events(repo: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """获取监控动态"""
    return await get_monitor_events(repo, limit)


async def _initial_refresh(subscription_id: int, target: str) -> None:
    """订阅创建后异步立即拉一次 repo 详情。"""
    try:
        await refresh_one_repo(target, subscription_id)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "Initial refresh failed for %s: %s", target, e
        )
