# -*- coding: utf-8 -*-
"""分析报告相关工具"""

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


async def report_list(date: str = None, limit: int = 30) -> ToolResponse:
    """获取报告列表

    Args:
        date: 可选，筛选特定日期
        limit: 返回数量

    Returns:
        ToolResponse: 报告列表
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {"limit": limit}
            if date:
                params["date"] = date
            resp = await client.get(f"{BASE_URL}/reports", params=params)
            if resp.status_code == 200:
                return _ok({"reports": resp.json()})
            return _err(f"获取失败: {resp.status_code}")
    except Exception as e:
        return _err(str(e))
