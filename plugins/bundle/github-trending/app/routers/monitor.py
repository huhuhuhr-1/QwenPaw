"""监控路由"""

from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import (
    get_subscriptions, add_subscription, delete_subscription, update_subscription,
    upload_monitor_events, get_monitor_events
)

router = APIRouter()


# ── 订阅管理 ──


class SubscriptionResponse(BaseModel):
    id: int
    target: str
    enabled: bool
    notify_enabled: bool


@router.get("/subscriptions")
async def list_subscriptions() -> List[Dict]:
    """获取订阅列表"""
    return await get_subscriptions()


@router.post("/subscriptions")
async def create_subscription(target: str) -> Dict:
    """添加订阅"""
    return await add_subscription(target)


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
