# -*- coding: utf-8 -*-
"""热榜相关工具"""

import json
import httpx
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

import os

BASE_URL = os.environ.get("QWENPAW_TOOL_BASE_URL", "http://127.0.0.1:8088")


def _ok(data: dict) -> ToolResponse:
    """把后端返回的 dict 包成 ToolResponse。"""
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))],
    )


def _err(msg: str) -> ToolResponse:
    """把错误消息包成 ToolResponse。"""
    return ToolResponse(content=[TextBlock(type="text", text=f"Error: {msg}")])


async def trending_get_daily(date: str = None, language: str = "all") -> ToolResponse:
    """获取每日热榜数据

    Args:
        date: 日期，格式 YYYY-MM-DD，默认今天
        language: 语言筛选，all/python/go 等

    Returns:
        ToolResponse: 热榜数据列表，包含 rank, name, stars, stars_delta 等
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"language": language}
            if date:
                params["date"] = date
            resp = await client.get(f"{BASE_URL}/trending/daily", params=params)
            if resp.status_code == 200:
                return _ok(resp.json())
            return _err(f"请求失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))


async def trending_get_dates(language: str = "all") -> ToolResponse:
    """获取有热榜数据的日期列表

    Args:
        language: 语言筛选

    Returns:
        ToolResponse: 日期列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{BASE_URL}/trending/dates", params={"language": language})
            if resp.status_code == 200:
                return _ok({"dates": resp.json()})
            return _err(f"请求失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))
