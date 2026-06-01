# -*- coding: utf-8 -*-
"""仓库相关工具"""

import json
import httpx
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

import os

BASE_URL = os.environ.get("QWENPAW_TOOL_BASE_URL", "http://127.0.0.1:8088")


def _ok(data: dict) -> ToolResponse:
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))],
    )


def _err(msg: str) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=f"Error: {msg}")])


async def repo_search(keyword: str, limit: int = 20) -> ToolResponse:
    """搜索 GitHub 仓库

    Args:
        keyword: 搜索关键词
        limit: 返回数量限制

    Returns:
        ToolResponse: 仓库列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BASE_URL}/repos/search",
                params={"keyword": keyword, "limit": limit},
            )
            if resp.status_code == 200:
                return _ok({"repos": resp.json()})
            return _err(f"搜索失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))


async def repo_detail(full_name: str) -> ToolResponse:
    """获取仓库详情

    Args:
        full_name: 仓库全名，格式 owner/repo

    Returns:
        ToolResponse: 仓库详细信息
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{BASE_URL}/repos/{full_name}")
            if resp.status_code == 200:
                return _ok(resp.json())
            return _err(f"获取失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))


async def repo_trend(full_name: str) -> ToolResponse:
    """获取仓库历史趋势

    Args:
        full_name: 仓库全名，格式 owner/repo

    Returns:
        ToolResponse: 仓库历史数据列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{BASE_URL}/repos/{full_name}/trend")
            if resp.status_code == 200:
                return _ok({"trend": resp.json()})
            return _err(f"获取失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))
