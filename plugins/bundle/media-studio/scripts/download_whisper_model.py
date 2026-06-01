#!/usr/bin/env python3
"""下载 faster-whisper 模型到 ~/.cache/qwenpaw/models/（与插件包分离）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from faster_whisper.utils import download_model

from app.services.transcribe.local_models import MODELS_ROOT, scan_local_models


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将 faster-whisper 模型下载到 ~/.cache/qwenpaw/models/ 目录",
    )
    parser.add_argument(
        "model",
        help="模型名，如 small、medium、large-v3",
    )
    parser.add_argument(
        "--alias",
        metavar="NAME",
        help="在模型目录下创建同名软链，便于配置（如 --alias whisper-large-v3）",
    )
    args = parser.parse_args()

    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot = Path(download_model(args.model, cache_dir=str(MODELS_ROOT)))
    print(f"已下载到: {snapshot}")

    if args.alias:
        link = MODELS_ROOT / args.alias
        if link.exists() or link.is_symlink():
            print(f"跳过软链（已存在）: {link}")
        else:
            link.symlink_to(snapshot, target_is_directory=True)
            print(f"已创建软链: {link}")

    print("\n当前可用模型：")
    for item in scan_local_models():
        print(f"  · {item['label']}: {item['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
