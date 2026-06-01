"""分析报告路由"""

from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import upload_report, get_reports, get_report

router = APIRouter()


class ReportContent(BaseModel):
    overview: Optional[str] = None
    highlights: Optional[List[Dict]] = None
    trends: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


class ReportUploadRequest(BaseModel):
    date: Optional[str] = None
    type: str = "daily_report"
    source: str = "llm"
    content: ReportContent


@router.post("")
async def create_report(data: ReportUploadRequest) -> Dict:
    """上传分析报告"""
    date_str = data.date or datetime.now().strftime("%Y-%m-%d")
    return await upload_report(date_str, data.type, data.content.model_dump(), data.source)


@router.get("")
async def list_reports(date: Optional[str] = None, limit: int = 30) -> List[Dict]:
    """获取报告列表"""
    return await get_reports(date, limit)


@router.get("/{report_id}")
async def get_report_detail(report_id: int) -> Optional[Dict]:
    """获取报告详情"""
    return await get_report(report_id)
