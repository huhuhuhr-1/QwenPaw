# -*- coding: utf-8 -*-
"""Docker 镜像搜索工具函数"""

import httpx
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

API_BASE = "https://docker.aityp.com/api/v1/image"


def search_docker_image(search: str, limit: int = 10, platform: str = "") -> ToolResponse:
    """搜索 Docker 镜像

    Args:
        search: 搜索关键词，如 nginx、mysql、redis、starrocks 等
        limit: 返回结果数量，默认为 10，最大 50
        platform: 平台架构过滤，如 "linux/amd64" 或 "linux/arm64"，为空则不限制

    Returns:
        ToolResponse: 包含镜像列表的文本结果，每条记录包括 source、mirror（华为云镜像）、platform、size、createdAt
    """
    try:
        params = {"search": search, "limit": min(limit, 50)}
        if platform:
            params["platform"] = platform

        resp = httpx.get(API_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            return ToolResponse(content=[
                TextBlock(type="text", text=f"未找到与「{search}」相关的镜像"),
            ])

        lines = [f"找到 {data.get('count', len(results))} 个镜像（显示前 {len(results)} 个）：\n"]
        for img in results:
            source = img.get("source", "?")
            mirror = img.get("mirror", "")
            platform_str = img.get("platform", "?")
            size = img.get("size", "?")
            created = img.get("createdAt", "?")[:10] if img.get("createdAt") else "?"

            line = f"  - {source}"
            if mirror:
                line += f"\n    镜像: {mirror}"
            line += f"\n    平台: {platform_str} | 大小: {size} | 创建: {created}"
            lines.append(line)

        return ToolResponse(content=[
            TextBlock(type="text", text="\n".join(lines)),
        ])
    except httpx.HTTPStatusError as e:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"API 请求失败（{e.response.status_code}）：{str(e)}"),
        ])
    except httpx.RequestError as e:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"网络请求失败：{str(e)}"),
        ])
    except Exception as e:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"搜索镜像失败：{str(e)}"),
        ])
