"""Unified transcribe worker pool (competitive consumption)."""

from __future__ import annotations


def transcribe_pool_size() -> int:
    """Total workers on the shared transcribe queue (only enabled lanes)."""
    from app.config import settings

    total = 0
    if settings.transcribe_fast_enabled:
        total += settings.max_concurrent_transcribe_fast
    if settings.transcribe_slow_enabled:
        total += settings.max_concurrent_transcribe_slow
    if settings.transcribe_external_enabled:
        total += settings.max_concurrent_transcribe_external
    return total
