# -*- coding: utf-8 -*-
"""订阅监控相关工具"""

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


async def monitor_list_subscriptions() -> ToolResponse:
    """获取订阅列表

    Returns:
        ToolResponse: 订阅列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{BASE_URL}/monitor/subscriptions")
            if resp.status_code == 200:
                return _ok({"subscriptions": resp.json()})
            return _err(f"获取失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))


async def monitor_get_events(repo: str = None, limit: int = 50) -> ToolResponse:
    """获取监控动态

    Args:
        repo: 可选，筛选特定仓库
        limit: 返回数量

    Returns:
        ToolResponse: 动态列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"limit": limit}
            if repo:
                params["repo"] = repo
            resp = await client.get(f"{BASE_URL}/monitor/events", params=params)
            if resp.status_code == 200:
                return _ok({"events": resp.json()})
            return _err(f"获取失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))
