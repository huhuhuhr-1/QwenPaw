# -*- coding: utf-8 -*-
"""分析报告相关工具"""

import httpx

BASE_URL = "http://127.0.0.1:7901"


async def report_upload(
    date: str = None,
    report_type: str = "daily_report",
    source: str = "llm",
    content: dict = None
) -> dict:
    """上传分析报告

    Args:
        date: 日期，默认今天
        report_type: 报告类型，daily_report/special_report
        source: 来源，llm/manual
        content: 报告内容，包含 overview, highlights, trends, suggestions

    Returns:
        上传结果
    """
    if content is None:
        return {"error": "content 不能为空"}

    async with httpx.AsyncClient(timeout=60) as client:
        data = {
            "date": date,
            "type": report_type,
            "source": source,
            "content": content
        }
        resp = await client.post(f"{BASE_URL}/reports", json=data)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"上传失败: {resp.status_code}"}


async def report_list(date: str = None, limit: int = 30) -> dict:
    """获取报告列表

    Args:
        date: 可选，筛选特定日期
        limit: 返回数量

    Returns:
        报告列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"limit": limit}
        if date:
            params["date"] = date
        resp = await client.get(f"{BASE_URL}/reports", params=params)
        if resp.status_code == 200:
            return {"reports": resp.json()}
        return {"error": f"获取失败: {resp.status_code}"}
