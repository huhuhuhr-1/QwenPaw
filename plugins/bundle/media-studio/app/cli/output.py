"""CLI output helpers — JSON by default for AI agents."""

from __future__ import annotations

import json
import sys
from typing import Any


def emit(data: Any, *, json_mode: bool = True) -> None:
    if json_mode:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        _emit_human(data)


def emit_error(message: str, *, code: int = 1, detail: Any = None, json_mode: bool = True) -> None:
    payload = {"ok": False, "error": message}
    if detail is not None:
        payload["detail"] = detail
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
    raise SystemExit(code)


def _emit_human(data: Any) -> None:
    if isinstance(data, dict):
        if data.get("workflow_id") and "steps" in data:
            print(f"workflow {data['workflow_id']}  status={data.get('status')}")
            for s in data.get("steps", []):
                err = f"  error={s['error']}" if s.get("error") else ""
                print(f"  [{s.get('status'):10}] {s.get('step_type')}{err}")
            return
        if data.get("workflow_id") and "files" in data:
            print(f"workflow {data['workflow_id']}  results:")
            for f in data["files"]:
                print(f"  {f.get('step_type'):14} {f.get('name')}  id={f.get('file_id')}")
            return
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if "workflow_id" in data[0]:
            for w in data:
                print(
                    f"{w.get('workflow_id')}  {w.get('entry_file_name')}  "
                    f"{w.get('status')}  {w.get('completed_count')}/{w.get('step_count')}"
                )
            return
        if "message" in data[0] and "level" in data[0]:
            for row in data:
                print(f"[{row.get('created_at')}] {row.get('level')} {row.get('step_type', '')} {row.get('message')}")
            return
    print(json.dumps(data, ensure_ascii=False, indent=2))
