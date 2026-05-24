# -*- coding: utf-8 -*-
"""获取当前系统时间"""

from datetime import datetime
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> ToolResponse:
    """获取当前系统时间

    Args:
        fmt: 时间格式，默认为 "%Y-%m-%d %H:%M:%S"（如 2026-05-20 20:50:00）
             常用格式：
             - "%Y-%m-%d %H:%M:%S" → 2026-05-20 20:50:00
             - "%Y-%m-%d"          → 2026-05-20
             - "%H:%M:%S"          → 20:50:00
             - "%Y年%m月%d日 %H:%M:%S" → 2026年05月20日 20:50:00
             - "%B %d, %Y"         → May 20, 2026

    Returns:
        ToolResponse: 包含格式化后的时间字符串
    """
    try:
        now = datetime.now()
        formatted = now.strftime(fmt)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"当前时间：{formatted}",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"获取时间失败：{str(e)}",
                ),
            ],
        )
