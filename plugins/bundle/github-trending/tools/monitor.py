# -*- coding: utf-8 -*-
"""订阅监控相关工具"""

import httpx

BASE_URL = "http://127.0.0.1:7901"


async def monitor_list_subscriptions() -> dict:
    """获取订阅列表

    Returns:
        订阅列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/monitor/subscriptions")
        if resp.status_code == 200:
            return {"subscriptions": resp.json()}
        return {"error": f"获取失败: {resp.status_code}"}


async def monitor_subscribe(repo: str) -> dict:
    """订阅一个 GitHub 仓库

    Args:
        repo: 仓库全名，格式 owner/repo

    Returns:
        订阅结果
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/monitor/subscriptions",
            params={"target": repo}
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"订阅失败: {resp.status_code}"}


async def monitor_unsubscribe(subscription_id: int) -> dict:
    """取消订阅

    Args:
        subscription_id: 订阅 ID

    Returns:
        操作结果
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{BASE_URL}/monitor/subscriptions/{subscription_id}")
        if resp.status_code == 200:
            return {"ok": True}
        return {"error": f"取消失败: {resp.status_code}"}


async def monitor_get_events(repo: str = None, limit: int = 50) -> dict:
    """获取监控动态

    Args:
        repo: 可选，筛选特定仓库
        limit: 返回数量

    Returns:
        动态列表
    """
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"limit": limit}
        if repo:
            params["repo"] = repo
        resp = await client.get(f"{BASE_URL}/monitor/events", params=params)
        if resp.status_code == 200:
            return {"events": resp.json()}
        return {"error": f"获取失败: {resp.status_code}"}


async def monitor_upload(
    repo: str,
    repo_info: dict,
    events: list
) -> dict:
    """上传监控数据

    Args:
        repo: 仓库全名
        repo_info: 仓库信息，包含 stars, forks, open_issues, language, description, last_commit
        events: 动态列表，每项包含 type, title, body, url, version, time

    Returns:
        上传结果
    """
    async with httpx.AsyncClient(timeout=60) as client:
        data = {
            "repo": repo,
            "repo_info": repo_info,
            "events": events
        }
        resp = await client.post(f"{BASE_URL}/monitor/upload", json=data)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"上传失败: {resp.status_code}"}
