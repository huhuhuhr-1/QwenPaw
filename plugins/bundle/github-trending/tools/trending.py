# -*- coding: utf-8 -*-
"""热榜相关工具"""

import httpx

BASE_URL = "http://127.0.0.1:7901"


async def trending_get_daily(date: str = None, language: str = "all") -> dict:
    """获取每日热榜数据

    Args:
        date: 日期，格式 YYYY-MM-DD，默认今天
        language: 语言筛选，all/python/go 等

    Returns:
        热榜数据列表，包含 rank, name, stars, stars_delta 等
    """
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"language": language}
        if date:
            params["date"] = date
        resp = await client.get(f"{BASE_URL}/trending/daily", params=params)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"请求失败: {resp.status_code}"}


async def trending_get_dates(language: str = "all") -> dict:
    """获取有热榜数据的日期列表

    Args:
        language: 语言筛选

    Returns:
        日期列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/trending/dates", params={"language": language})
        if resp.status_code == 200:
            return {"dates": resp.json()}
        return {"error": f"请求失败: {resp.status_code}"}


async def trending_upload(
    date: str = None,
    language: str = "all",
    summary: str = None,
    items: list = None
) -> dict:
    """上传热榜数据到存储

    Args:
        date: 日期，默认今天
        language: 语言
        summary: 热榜摘要
        items: 热榜项目列表，每项包含 rank, name, owner, full_name, description, language, stars, stars_delta, forks, url, analysis

    Returns:
        上传结果
    """
    if items is None:
        return {"error": "items 不能为空"}

    async with httpx.AsyncClient(timeout=60) as client:
        data = {
            "date": date,
            "language": language,
            "summary": summary,
            "items": items
        }
        resp = await client.post(f"{BASE_URL}/trending/upload", json=data)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"上传失败: {resp.status_code}", "detail": resp.text}
