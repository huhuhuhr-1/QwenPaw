# -*- coding: utf-8 -*-
"""Debug 启动脚本 - 用于 PyCharm 调试

用法:
    1. PyCharm: Run -> Edit Configurations -> + -> Python
       Script path: /opt/github/QwenPaw/src/qwenpaw/run_debug.py
       Working directory: /opt/github/QwenPaw

    2. 或直接运行: python run_debug.py
"""
import os
import sys

# 确保 src 目录在 path 中
sys.path.insert(0, "/opt/github/QwenPaw/src")

# 设置调试模式环境变量
os.environ.setdefault("QWENPAW_LOG_LEVEL", "debug")
os.environ.setdefault("QWENPAW_WORKING_DIR", "/home/hr/.qwenpaw")

if __name__ == "__main__":
    import uvicorn
    from qwenpaw.app._app import app

    # uvicorn 直接启动 FastAPI 应用
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=18088,
        log_level="debug",
    )
