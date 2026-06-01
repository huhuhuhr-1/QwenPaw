"""仓库路由"""

from typing import List, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import search_repos, get_repo, get_repo_trend

router = APIRouter()


@router.get("/search")
async def search(keyword: str, limit: int = 20) -> List[Dict]:
    """搜索项目"""
    return await search_repos(keyword, limit)


@router.get("/{full_name:path}")
async def get_repo_detail(full_name: str) -> Optional[Dict]:
    """获取项目详情"""
    return await get_repo(full_name)


@router.get("/{full_name:path}/trend")
async def get_trend(full_name: str) -> List[Dict]:
    """获取项目趋势"""
    return await get_repo_trend(full_name)
