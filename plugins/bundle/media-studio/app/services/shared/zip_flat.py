"""Flat zip entry names (no nested directories)."""

from __future__ import annotations

from pathlib import Path


def flat_arc_name(
    original_name: str,
    seen: set[str],
    *,
    prefix: str | None = None,
) -> str:
    """Return a unique zip member path with no directory separators."""
    base = Path(original_name).name
    candidates: list[str] = [base]
    if prefix:
        candidates.append(f"{prefix}_{base}")

    for arc in candidates:
        if arc not in seen:
            seen.add(arc)
            return arc

    stem = Path(candidates[-1]).stem
    suf = Path(candidates[-1]).suffix
    n = 1
    while True:
        arc = f"{stem}_{n}{suf}"
        if arc not in seen:
            seen.add(arc)
            return arc
        n += 1
