# -*- coding: utf-8 -*-
"""Docker Image Search — 搜索 Docker 镜像，查询版本信息和国内镜像"""

import importlib.util
import os
from qwenpaw.plugins.api import PluginApi

__all__ = ["plugin"]


def _load_tool_module():
    module_name = "docker_search_tool"
    module_path = os.path.join(os.path.dirname(__file__), "docker_search_tool.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DockerSearchPlugin:
    def register(self, api: PluginApi):
        tool = _load_tool_module()
        api.register_tool(
            tool_name="search_docker_image",
            tool_func=tool.search_docker_image,
            description="搜索 Docker 镜像，支持关键词搜索、数量限制和平台架构过滤。返回镜像的 source（源地址）、mirror（华为云镜像地址）、platform（平台架构）、size（大小）、createdAt（创建时间）。",
            icon="🐳",
        )


plugin = DockerSearchPlugin()
