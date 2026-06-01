"""Scan and resolve faster-whisper models under ~/.cache/qwenpaw/models/."""

from __future__ import annotations

import os
from pathlib import Path

MODELS_ROOT = Path.home() / ".cache" / "qwenpaw" / "models"


def resolve_model_dir(entry: Path) -> Path | None:
    """Return directory that contains model.bin (direct dir or HF snapshot)."""
    try:
        entry = entry.resolve()
    except OSError:
        return None
    if not entry.is_dir():
        return None
    if (entry / "model.bin").is_file():
        return entry
    snapshots = entry / "snapshots"
    if snapshots.is_dir():
        candidates = [
            p
            for p in snapshots.iterdir()
            if p.is_dir() and (p / "model.bin").is_file()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]
    return None


def _label_for(entry_name: str) -> str:
    if entry_name.startswith("models--") and "faster-whisper-" in entry_name:
        return entry_name.split("faster-whisper-", 1)[-1]
    return entry_name


def _entry_config_path(entry_name: str) -> str:
    return f"models/{entry_name}"


def scan_local_models() -> list[dict[str, str]]:
    """List models ready to load from models/ (value = models/<name>, label for UI)."""
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, str]] = []

    for entry in sorted(MODELS_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not entry.exists():
            continue
        if not entry.is_dir() and not entry.is_symlink():
            continue
        if resolve_model_dir(entry) is None:
            continue
        items.append({"value": _entry_config_path(entry.name), "label": _label_for(entry.name)})

    items.sort(key=lambda x: x["label"].lower())
    return items


def resolve_configured_model_path(model_path: str) -> Path | None:
    """Resolve configured path to a directory containing model.bin."""
    raw = (model_path or "").strip()
    if not raw:
        return None

    p = Path(raw)
    if not p.is_absolute():
        p = (MODELS_ROOT / raw).resolve()
    else:
        p = p.resolve()

    if (p / "model.bin").is_file():
        return p

    # models/<entry> — HF 缓存或软链，快照可能在 models/ 外
    prefix = f"models{os.sep}" if os.sep != "/" else "models/"
    rel = raw.replace("\\", "/")
    if rel.startswith("models/"):
        entry = MODELS_ROOT / rel.split("/", 1)[1].split("/")[0]
        if entry.exists():
            found = resolve_model_dir(entry)
            if found:
                return found.resolve()

    if p.is_dir():
        found = resolve_model_dir(p)
        return found.resolve() if found else None
    return None


def is_local_model_ready(model_path: str) -> bool:
    return resolve_configured_model_path(model_path) is not None


def is_valid_local_model_path(model_path: str) -> bool:
    """Configured path must refer to a top-level entry under models/."""
    raw = (model_path or "").strip().replace("\\", "/")
    if not raw.startswith("models/"):
        return False
    name = raw.split("/", 1)[1].split("/")[0]
    entry = MODELS_ROOT / name
    return entry.exists() and resolve_model_dir(entry) is not None
