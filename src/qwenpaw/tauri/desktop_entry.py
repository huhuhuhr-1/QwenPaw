# -*- coding: utf-8 -*-
"""Desktop entry point for qwenpaw-desktop deb package.

Directly starts the FastAPI backend in a thread, then opens a pywebview
window. This avoids the "subprocess + -m" pattern used by desktop_cmd.py
which doesn't work in PyInstaller environments where sys.executable is
a frozen bootloader.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import socket
import sys
import threading
import traceback

logger = logging.getLogger(__name__)


def _find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        return sock.getsockname()[1]


def _start_backend(host: str, port: int, log_level: str) -> None:
    """Start uvicorn FastAPI server in a daemon thread."""
    import uvicorn

    from qwenpaw.config.utils import write_last_api
    from qwenpaw.constant import LOG_LEVEL_ENV
    from qwenpaw.utils.logging import SuppressPathAccessLogFilter, setup_logger

    os.environ[LOG_LEVEL_ENV] = log_level
    setup_logger(log_level)

    logging.getLogger("uvicorn.access").addFilter(
        SuppressPathAccessLogFilter(["/console/push-messages"]),
    )

    config = uvicorn.Config(
        "qwenpaw.app._app:app",
        host=host,
        port=port,
        reload=False,
        workers=1,
        log_level=log_level,
    )
    try:
        write_last_api(host, port)
        uvicorn.Server(config).run()
    except Exception:
        logger.exception("Backend server failed")


def _wait_for_http(host: str, port: int, timeout_sec: float = 60.0) -> bool:
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((host, port))
                return True
        except (OSError, socket.error):
            time.sleep(0.5)
    return False


def main() -> None:
    print("[desktop_entry] Starting...", flush=True)

    host = "127.0.0.1"
    log_level = "info"

    # Parse --log-level from command line
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--log-level" and i + 1 < len(args):
            log_level = args[i + 1]
            break

    port = _find_free_port(host)
    url = f"http://{host}:{port}"
    print(f"[desktop_entry] Port={port}, starting backend thread...", flush=True)

    # Start backend in background thread
    backend_thread = threading.Thread(
        target=_start_backend,
        args=(host, port, log_level),
        daemon=True,
    )
    backend_thread.start()

    # Wait for backend to be ready
    print("[desktop_entry] Waiting for HTTP...", flush=True)
    if not _wait_for_http(host, port, timeout_sec=60.0):
        print("[desktop_entry] ERROR: Backend timeout", flush=True)
        sys.exit(1)

    print("[desktop_entry] HTTP ready, importing webview...", flush=True)

    # For pywebview/GTK, we need to use system Python's gi module
    # which is at /usr/lib/python3/dist-packages
    # Remove _internal paths temporarily so system gi is used
    _internal_paths = [p for p in sys.path if '_internal' in p]
    for p in _internal_paths:
        sys.path.remove(p)
    # Also put system site-packages first
    sys.path.insert(0, '/usr/lib/python3/dist-packages')

    try:
        import webview
        print(f"[desktop_entry] webview imported: {webview.__file__}", flush=True)
    except ImportError as e:
        print(f"[desktop_entry] ERROR: webview not available: {e}", flush=True)
        sys.exit(1)

    print("[desktop_entry] Creating window...", flush=True)
    try:
        webview.create_window(
            "QwenPaw Desktop",
            url,
            width=1280,
            height=800,
            text_select=True,
        )
        print("[desktop_entry] Window created, calling start...", flush=True)
        webview.start(private_mode=False)
        print("[desktop_entry] webview.start() returned", flush=True)
    except Exception as e:
        print(f"[desktop_entry] ERROR: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    mp.freeze_support()
    main()