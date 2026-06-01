# QwenPaw 工具插件开发手册

> **本文档定位**：工具插件（Agent 可调用的函数）开发指南
>
> **快速入门** → [README.md](README.md) | **Bundle 插件开发** → [plugin-dev.md](plugin-dev.md)

## 目录

1. [什么是工具插件](#1-什么是工具插件)
2. [目录结构](#2-目录结构)
3. [plugin.json 元数据](#3-pluginjson-元数据)
4. [入口文件 (plugin.py)](#4-入口文件-pluginpy)
5. [工具函数 (_tool.py)](#5-工具函数-_toolpy)
6. [获取用户配置](#6-获取用户配置)
7. [工具响应格式](#7-工具响应格式)
8. [完整示例：time_now](#8-完整示例time_now)
9. [完整示例：wan27](#9-完整示例wan27)
10. [常见问题](#10-常见问题)

---

## 1. 什么是工具插件

工具插件（Tool Plugin）向 Agent 注册可供调用的工具函数（Function Calling），让 Agent 能执行特定操作，例如生成图片、获取时间、调用外部 API 等。

区别于 bundle 插件（提供完整前后端 + 技能），工具插件：

- **只有后端，没有前端** — 不需要前端构建
- **注册到 Agent 的工具箱** — Agent 在 ReAct 循环中可调用
- **支持配置字段** — 用户可在界面中配置 API Key、endpoint 等
- **轻量** — 通常一个 `plugin.py` + 一个 `_tool.py` 文件

工具插件在 QwenPaw 中的位置：

```
plugins/<tool-id>/     ← 工具插件放在 plugins/ 下
plugins/<plugin-id>/   ← bundle 插件也放在 plugins/ 下
```

---

## 2. 目录结构

最小的工具插件只需要两个文件：

```
plugins/<tool-id>/
├── plugin.json          # 元数据（必需）
├── <tool-id>.py         # 入口文件（必需，export plugin 对象）
├── <tool-id>_tool.py    # 工具函数实现（可选，可拆分）
└── requirements.txt     # Python 依赖（可选）
```

示例（time_now）：

```
plugins/tool/time_now/
├── plugin.json           # 元数据
├── time_now.py           # 入口，export plugin 对象
└── time_now_tool.py      # 工具函数实现
```

示例（wan27，多工具）：

```
plugins/tool/wan27/
├── plugin.json
├── wan27.py
└── wan27_tool.py
```

---

## 3. plugin.json 元数据

### 3.1 最小配置

```json
{
  "id": "my-tool",
  "name": "My Tool",
  "version": "1.0.0",
  "type": "tool",
  "description": "Tool description",
  "entry": {
    "backend": "my_tool.py"
  },
  "dependencies": [],
  "meta": {
    "tools": [
      {
        "name": "my_tool_func",
        "description": "Function description for agent",
        "icon": "🔧",
        "requires_config": false,
        "config_fields": []
      }
    ]
  }
}
```

### 3.2 带配置字段的工具

```json
{
  "id": "my-tool",
  "name": "My Tool",
  "type": "tool",
  "entry": {
    "backend": "my_tool.py"
  },
  "dependencies": ["httpx>=0.24.0"],
  "meta": {
    "tools": [
      {
        "name": "my_tool_func",
        "description": "Tool description for agent prompt",
        "icon": "🎨",
        "requires_config": true,
        "config_fields": [
          {
            "name": "api_key",
            "label": "API Key",
            "type": "password",
            "required": true,
            "placeholder": "sk-...",
            "help": "Get your API key from ..."
          },
          {
            "name": "endpoint",
            "label": "API Endpoint",
            "type": "text",
            "required": false,
            "placeholder": "https://api.example.com/v1"
          },
          {
            "name": "model",
            "label": "Model",
            "type": "select",
            "required": false,
            "default": "model-v1",
            "options": ["model-v1", "model-v2", "model-v3"]
          },
          {
            "name": "timeout",
            "label": "Request Timeout",
            "type": "number",
            "required": false,
            "placeholder": "60",
            "min": 10,
            "max": 300
          }
        ]
      }
    ],
    "api_key_url": "https://example.com/api-keys",
    "api_key_hint": "Get your API key from example.com"
  }
}
```

### 3.3 字段说明

| 字段 | 说明 |
|------|------|
| `type` | 必须为 `"tool"`，区别于 bundle 插件的 `"frontend"`/`"general"` |
| `entry.backend` | Python 入口文件，**必须 export `plugin` 对象** |
| `dependencies` | UI 展示用。**实际安装**看 `requirements.txt` |
| `meta.tools[]` | 工具定义列表。一个插件可以注册多个工具 |
| `meta.tools[].name` | 工具函数名，**必须与 `api.register_tool()` 的 `tool_name` 一致** |
| `meta.tools[].requires_config` | 是否需要配置才能使用 |
| `meta.tools[].config_fields[]` | 配置字段定义，会自动生成配置 UI |

### 3.4 config_fields 类型

| `type` | 对应 UI | 额外字段 |
|--------|---------|----------|
| `"text"` | 文本输入框 | `label`, `required`, `placeholder`, `help` |
| `"password"` | 密码输入框 | 同上 |
| `"number"` | 数字输入 | + `min`, `max` |
| `"select"` | 下拉选择 | + `options: [...]`, `default` |

---

## 4. 入口文件 (plugin.py)

所有工具插件的入口文件结构一致：

```python
# my_tool.py
import importlib.util
import os
from qwenpaw.plugins.api import PluginApi

__all__ = ["plugin"]


def _load_tool_module():
    """动态加载同目录下的 _tool.py"""
    module_name = "my_tool_tool"
    module_path = os.path.join(os.path.dirname(__file__), "my_tool_tool.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MyToolPlugin:
    def register(self, api: PluginApi):
        tool = _load_tool_module()

        api.register_tool(
            tool_name="my_tool_func",
            tool_func=tool.my_tool_func,
            description="What this tool does (shown to agent)",
            icon="🔧",
        )


plugin = MyToolPlugin()
```

### 4.1 register_tool 参数

`api.register_tool()` 定义在 `src/qwenpaw/plugins/api.py:287-400`：

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | str | 工具函数名，**必须唯一**，Agent 通过此名调用 |
| `tool_func` | Callable | 实际的工具函数实现 |
| `description` | str | 描述，Agent 用来判断何时调用此工具 |
| `icon` | str | 显示图标（emoji），默认 "🔧" |
| `enabled` | bool | 默认是否启用。建议 `False` 让用户手动启用 |

### 4.2 注册时序

`register_tool()` 不会立即注册，而是通过注册一个 **startup hook** 延迟执行：

```
plugin.register(api)
  → api.register_tool("my_func", my_func, ...)
    → api.register_startup_hook("register_tool_<plugin_id>_<tool_name>")
      → 启动时将 my_func 注入到 qwenpaw.agents.tools 模块
      → 同时在 agent config 中添加 BuiltinToolConfig
```

源码参考：

```python
# api.py:329-396
def register_tool(self, tool_name, tool_func, ...):
    def _startup_register():
        import qwenpaw.agents.tools as tools_module
        setattr(tools_module, tool_name, tool_func)    # 注入 tools 模块
        tools_module.__all__.append(tool_name)
        # 添加 agent config
        agent_config.tools.builtin_tools[tool_name] = BuiltinToolConfig(...)

    self.register_startup_hook(
        hook_name=f"register_tool_{self.plugin_id}_{tool_name}",
        callback=_startup_register,
        priority=50,
    )
```

---

## 5. 工具函数 (_tool.py)

### 5.1 函数签名

工具函数接收 Agent 传来的参数，返回 `ToolResponse`：

```python
from agentscope.message import TextBlock, ImageBlock, VideoBlock, AudioBlock
from agentscope.tool import ToolResponse


def my_tool_func(param1: str, param2: int = 10) -> ToolResponse:
    """工具描述 — Agent 根据此描述判断何时调用。

    Args:
        param1: 参数1说明
        param2: 参数2说明，默认 10

    Returns:
        ToolResponse: 包含处理结果
    """
    try:
        result = do_something(param1, param2)
        return ToolResponse(
            content=[
                TextBlock(type="text", text=f"结果：{result}"),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(type="text", text=f"失败：{str(e)}"),
            ],
        )
```

> **注意**：函数签名中的类型注解和 docstring 会被解析为 Agent 的 function calling schema。参数名和描述要清晰，否则 Agent 不知道怎么传参。

### 5.2 返回值类型

`ToolResponse` 的 `content` 是 `ContentBlock` 列表，支持多种类型：

| Block 类型 | 用途 | 导入 |
|------------|------|------|
| `TextBlock` | 文本回复 | `from agentscope.message import TextBlock` |
| `ImageBlock` | 图片 | `from agentscope.message import ImageBlock` |
| `VideoBlock` | 视频 | `from agentscope.message import VideoBlock` |
| `AudioBlock` | 音频 | `from agentscope.message import AudioBlock` |

示例：

```python
# 多类型返回
ToolResponse(content=[
    TextBlock(type="text", text="处理完成，生成结果如下："),
    ImageBlock(type="image", url="file:///path/to/image.png"),
])
```

### 5.3 错误处理

工具函数必须自己处理异常，不要抛出未捕获的异常：

```python
def safe_tool() -> ToolResponse:
    try:
        # 可能会失败的操作
        ...
        return ToolResponse(content=[TextBlock(type="text", text="成功")])
    except Exception as e:
        # 返回友好的错误信息，让 Agent 知道发生了什么
        return ToolResponse(content=[
            TextBlock(type="text", text=f"操作失败：{str(e)}"),
        ])
```

---

## 6. 获取用户配置

对于需要 API Key 等配置的工具，通过 `get_tool_config()` 获取用户设置：

```python
from qwenpaw.plugins import get_tool_config

def my_tool() -> ToolResponse:
    # 获取当前 agent 对此工具的配置
    tool_config = get_tool_config("my_tool_func")

    if not tool_config:
        return ToolResponse(content=[
            TextBlock(type="text", text="工具未配置，请在设置中填写 API Key"),
        ])

    api_key = tool_config.get("api_key")
    endpoint = tool_config.get("endpoint", "https://default.example.com")
    timeout = tool_config.get("timeout", 60)

    # 使用配置调用外部 API
    ...
```

配置来源：
1. 用户在插件 UI 中填写的 `config_fields`
2. 存储在 `plugin.json` 的 `meta.tools[].config_fields[]` 定义的结构中

`get_tool_config` 的实现在 `api.py:10-45`：

```python
def get_tool_config(tool_name: str) -> Optional[Dict]:
    agent_id = get_current_agent_id()
    registry = PluginRegistry()
    return registry.get_tool_config(tool_name, agent_id)
```

---

## 7. 工具响应格式

Agent 工具函数的标准返回格式：

| 场景 | 返回 |
|------|------|
| 成功 | `ToolResponse(content=[TextBlock(type="text", text="...")])` |
| 失败（可恢复） | `ToolResponse(content=[TextBlock(type="text", text="失败原因")])` |
| 未配置 | `ToolResponse(content=[TextBlock(type="text", text="请先配置...")])` |
| 生成图片 | `ToolResponse(content=[ImageBlock(type="image", url="...")])` |
| 生成视频 | `ToolResponse(content=[VideoBlock(type="video", url="...")])` |

Agent 在 ReAct 循环中收到 `ToolResponse` 后，会根据 `content` 中的文本回复用户或继续执行下一步。

---

## 8. 完整示例：time_now

### plugin.json

```json
{
  "id": "time_now",
  "name": "Current Time",
  "version": "1.0.0",
  "type": "tool",
  "description": "获取当前系统时间",
  "entry": { "backend": "time_now.py" },
  "dependencies": [],
  "meta": {
    "tools": [{
      "name": "get_current_time",
      "description": "获取当前系统时间，支持格式化输出",
      "icon": "🕐",
      "requires_config": false,
      "config_fields": []
    }]
  }
}
```

### time_now.py

```python
import importlib.util, os
from qwenpaw.plugins.api import PluginApi

__all__ = ["plugin"]


def _load_tool_module():
    path = os.path.join(os.path.dirname(__file__), "time_now_tool.py")
    spec = importlib.util.spec_from_file_location("time_now_tool", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TimeNowPlugin:
    def register(self, api: PluginApi):
        tool = _load_tool_module()
        api.register_tool(
            tool_name="get_current_time",
            tool_func=tool.get_current_time,
            description="获取当前系统时间，支持自定义格式",
            icon="🕐",
        )


plugin = TimeNowPlugin()
```

### time_now_tool.py

```python
from datetime import datetime
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> ToolResponse:
    """获取当前系统时间

    Args:
        fmt: 时间格式，默认为 "%Y-%m-%d %H:%M:%S"

    Returns:
        ToolResponse: 包含格式化后的时间字符串
    """
    try:
        now = datetime.now()
        formatted = now.strftime(fmt)
        return ToolResponse(content=[
            TextBlock(type="text", text=f"当前时间：{formatted}"),
        ])
    except Exception as e:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"获取时间失败：{str(e)}"),
        ])
```

---

## 9. 完整示例：wan27（带配置的多工具插件）

### plugin.json 关键部分

```json
{
  "id": "wan27-tool",
  "type": "tool",
  "entry": { "backend": "wan27.py" },
  "dependencies": ["dashscope>=1.25.16", "httpx>=0.24.0"],
  "meta": {
    "tools": [
      {
        "name": "text_to_video_wan",
        "description": "Generate videos from text prompts using Wan 2.7",
        "icon": "🎬",
        "requires_config": true,
        "config_fields": [
          { "name": "api_key", "label": "DashScope API Key", "type": "password", "required": true },
          { "name": "endpoint", "label": "API Endpoint", "type": "text" },
          { "name": "timeout", "label": "Timeout", "type": "number", "default": 600 }
        ]
      }
    ]
  }
}
```

### wan27.py 入口

```python
import importlib.util, os, logging
from qwenpaw.plugins.api import PluginApi

logger = logging.getLogger(__name__)


def _load_tool_module():
    path = os.path.join(os.path.dirname(__file__), "wan27_tool.py")
    spec = importlib.util.spec_from_file_location("wan27_tool", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Wan27ToolPlugin:
    def register(self, api: PluginApi):
        tool = _load_tool_module()
        api.register_tool("text_to_video_wan", tool.text_to_video_wan, "Generate videos from text", icon="🎬")
        api.register_tool("image_to_video_wan", tool.image_to_video_wan, "Generate videos from images", icon="🎞️")
        api.register_tool("reference_to_video_wan", tool.reference_to_video_wan, "Generate videos with character references", icon="🎭")


plugin = Wan27ToolPlugin()
```

### wan27_tool.py 工具函数中使用配置

```python
import httpx
from agentscope.message import TextBlock, VideoBlock
from agentscope.tool import ToolResponse
from qwenpaw.plugins import get_tool_config


def text_to_video_wan(prompt: str, resolution: str = "720P") -> ToolResponse:
    """Generate videos from text prompts using Wan 2.7.

    Args:
        prompt: Text description of the video to generate.
        resolution: Video resolution. "720P" or "1080P".

    Returns:
        ToolResponse with video path.
    """
    try:
        # 获取用户配置
        tool_config = get_tool_config("text_to_video_wan")
        if not tool_config:
            return ToolResponse(content=[
                TextBlock(type="text", text="请先在工具设置中配置 API Key"),
            ])

        api_key = tool_config.get("api_key")
        endpoint = tool_config.get("endpoint", "https://dashscope.aliyuncs.com/api/v1")
        timeout = tool_config.get("timeout", 600)

        # 调用 API ...
        result = _call_api(api_key, endpoint, prompt, resolution, timeout)

        return ToolResponse(content=[
            TextBlock(type="text", text=f"视频已生成"),
            VideoBlock(type="video", url=result["url"]),
        ])
    except Exception as e:
        return ToolResponse(content=[
            TextBlock(type="text", text=f"生成失败：{str(e)}"),
        ])
```

---

## 10. 常见问题

### Q1: 工具注册后 Agent 看不到

**原因**：
- `register_tool` 的 `enabled` 默认为 `False`，需要用户手动启用
- 启动钩子未执行（需重启 QwenPaw）

**解决**：
- 用户去插件设置页面手动启用工具
- 检查启动日志是否有 `Registered tool function` 日志

### Q2 (共用): `requirements.txt` 第一行依赖永远不生效

**原因**：`requirements.txt` 文件开头包含 UTF-8 BOM（`EF BB BF` 三个隐藏字节），`str.strip()` 删不掉 BOM，导致 `Requirement('﻿fastapi==...')` 解析失败后被 `except Exception: continue` 静默跳过。

**症状**：插件反复尝试安装依赖，或提示 "Plugin loader is not ready yet"。

**解决**：用支持 UTF-8 无 BOM 的编辑器（如 VS Code）重新保存 `requirements.txt`，或手动删除文件首部的 BOM 字符：

```bash
# 检测
head -c 3 requirements.txt | xxd | grep "efbb bf" && echo "有BOM" || echo "无BOM"
# 移除
sed -i '1s/^\xEF\xBB\xBF//' requirements.txt
```

### Q3 (共用): `TypeError: 'typing.Self' is not valid as a type annotation`

**原因**：QwenPaw 仍使用 Python 3.10，`typing.Self` / `types.SelfType` 仅在 Python 3.11+ 可用。

**解决**：
```python
# ❌ Python 3.11+
from typing import Self
def my_method(self) -> Self: ...

# ✅ Python 3.10 兼容
from typing import TypeVar
T = TypeVar("T", bound="MyClass")
def my_method(self) -> "MyClass": ...
```

### Q4 (共用): `requirements.txt` 与 `plugin.json.dependencies` 漂移

**原因**：两处单独维护，时间一长容易出现"代码 import 但 requirements 没装"或"装了但 plugin.json 没声明 UI 看不见"。

**解决**：
- 每次发布前 diff 两文件包名
- 在 CI 加自动检查（grep `requirements.txt` 的包名是否都出现在 `dependencies`）

### Q2: Agent 调用工具时报参数错误

**原因**：函数的 docstring 和类型注解会被解析为 function calling schema。如果参数名/描述模糊，Agent 会传错参数。

**解决**：
```python
# ✅ 清晰
def generate(prompt: str, resolution: str = "720P") -> ToolResponse:
    """Generate video with given prompt.

    Args:
        prompt: Text description of the video. Be specific about style and content.
        resolution: Video quality. "720P" or "1080P".
    """

# ❌ 模糊
def generate(a: str, b: str = "") -> ToolResponse:
    """generate"""
```

### Q3: 工具函数抛出未捕获异常

**原因**：函数内未做 `try/except`，异常传播到 Agent 导致调用失败。

**解决**：所有工具函数内部用 `try/except` 包裹逻辑，返回友好的 `ToolResponse`。

### Q4: `get_tool_config()` 返回 None

**原因**：
- `requires_config: false` 时配置不会被保存
- 用户未在 UI 中填写配置
- 当前 agent 上下文不对

**解决**：
- 确保 `plugin.json` 中 `requires_config: true`
- 让用户在 UI 中填写并保存配置
- 检查是否有当前 agent ID

### Q5: plugin.json 和 register_tool 的 `tool_name` 不一致

**原因**：`plugin.json` 中 `meta.tools[].name` 和 `api.register_tool(tool_name=...)` 必须完全一致。

**解决**：保持两端一致。

### Q6: 依赖安装了但工具运行时报 `ModuleNotFoundError`

**原因**：`requirements.txt` 中的依赖通过 pip install 装到了 QwenPaw 的 Python 环境，但依赖安装时出错或未自动触发。

**解决**：
- 手动执行 `pip install -r requirements.txt`
- 检查插件日志中是否有 `Installing dependencies for plugin` 行
- 确认 `requirements.txt` 存在于插件根目录

---

## 附录：代码文件参考

| 文件 | 用途 |
|------|------|
| `src/qwenpaw/plugins/api.py` | `PluginApi.register_tool()` — 工具注册 API |
| `src/qwenpaw/plugins/api.py` | `get_tool_config()` — 运行时获取用户配置 |
| `src/qwenpaw/plugins/loader.py` | `PluginLoader.load_plugin()` — 插件加载和依赖安装 |
| `plugins/tool/time_now/time_now.py` | 最小工具插件入口示例 |
| `plugins/tool/time_now/time_now_tool.py` | 最小工具函数示例 |
| `plugins/tool/wan27/wan27.py` | 多工具插件入口示例 |
| `plugins/tool/wan27/wan27_tool.py` | 多工具 + 配置读取示例 |
