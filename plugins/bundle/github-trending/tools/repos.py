# -*- coding: utf-8 -*-
"""仓库相关工具"""

import httpx

BASE_URL = "http://127.0.0.1:7901"


async def repo_search(keyword: str, limit: int = 20) -> dict:
    """搜索 GitHub 仓库

    Args:
        keyword: 搜索关键词
        limit: 返回数量限制

    Returns:
        仓库列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/repos/search",
            params={"keyword": keyword, "limit": limit}
        )
        if resp.status_code == 200:
            return {"repos": resp.json()}
        return {"error": f"搜索失败: {resp.status_code}"}


async def repo_detail(full_name: str) -> dict:
    """获取仓库详情

    Args:
        full_name: 仓库全名，格式 owner/repo

    Returns:
        仓库详细信息
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/repos/{full_name}")
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"获取失败: {resp.status_code}"}


async def repo_trend(full_name: str) -> dict:
    """获取仓库历史趋势

    Args:
        full_name: 仓库全名，格式 owner/repo

    Returns:
        仓库历史数据列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/repos/{full_name}/trend")
        if resp.status_code == 200:
            return {"trend": resp.json()}
        return {"error": f"获取失败: {resp.status_code}"}
