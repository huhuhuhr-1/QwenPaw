"""热榜路由"""

from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import (
    upload_trending, get_daily_trending, get_available_dates,
    upsert_repo
)

router = APIRouter()


class TrendingUploadItem(BaseModel):
    rank: int
    name: str
    owner: str
    full_name: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    stars_delta: int = 0
    forks: int = 0
    url: str
    analysis: Optional[str] = None


class TrendingUploadRequest(BaseModel):
    date: Optional[str] = None  # 默认今天
    language: str = "all"
    summary: Optional[str] = None
    items: List[TrendingUploadItem]


class TrendingResponse(BaseModel):
    date: str
    language: str
    total_count: int
    updated_count: int
    summary: Optional[str] = None
    items: List[Dict]


@router.post("/upload")
async def upload(data: TrendingUploadRequest):
    """上传热榜数据"""
    date_str = data.date or datetime.now().strftime("%Y-%m-%d")
    items = [item.model_dump() for item in data.items]

    # 同步更新仓库索引
    for item in items:
        await upsert_repo(item)

    result = await upload_trending(date_str, data.language, items, data.summary)
    return result


@router.get("/daily")
async def get_daily(date: Optional[str] = None, language: str = "all") -> Optional[TrendingResponse]:
    """获取某天热榜"""
    return await get_daily_trending(date, language)


@router.get("/dates")
async def list_dates(language: str = "all") -> List[str]:
    """获取有数据的日期列表"""
    return await get_available_dates(language)
