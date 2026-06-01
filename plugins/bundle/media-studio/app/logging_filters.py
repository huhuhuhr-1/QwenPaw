"""Reduce noise from stray WebSocket probes on the HTTP API (no WS routes)."""

import logging


class SuppressStrayWebSocket403Filter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "403" not in msg:
            return True
        if "WebSocket" in msg and "403" in msg:
            return False
        if "connection rejected" in msg and "Forbidden" in msg:
            return False
        return True


def install_uvicorn_log_filters() -> None:
    filt = SuppressStrayWebSocket403Filter()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(filt)
