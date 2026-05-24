# -*- coding: utf-8 -*-
"""Current Time Plugin - 获取当前系统时间"""

import importlib.util
import os
from qwenpaw.plugins.api import PluginApi

__all__ = ["plugin"]


def _load_tool_module():
    """动态加载同目录下的 time_now_tool.py"""
    module_name = "time_now_tool"
    module_path = os.path.join(os.path.dirname(__file__), "time_now_tool.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TimeNowPlugin:
    """时间插件"""

    def register(self, api: PluginApi):
        """注册时间工具"""
        tool_module = _load_tool_module()

        api.register_tool(
            tool_name="get_current_time",
            tool_func=tool_module.get_current_time,
            description="获取当前系统时间，支持自定义格式。参数 fmt 是 Python 时间格式化字符串。",
            icon="🕐",
        )


plugin = TimeNowPlugin()
