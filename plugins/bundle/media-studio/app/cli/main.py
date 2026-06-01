"""
media-studio CLI — machine-friendly interface for scripts and AI agents.

Default output is JSON on stdout. Use --pretty for human-readable text.

Examples:
  processor health
  processor upload ./video.mp4
  processor workflow run ./video.mp4 --wait --save-dir ./out
  processor workflow get <workflow_id>
  processor workflow wait <workflow_id> --timeout 3600
  processor file cat <file_id>
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

from app.cli.client import ProcessorAPIError, ProcessorClient
from app.cli.output import emit, emit_error

DEFAULT_API = os.environ.get("MEDIA_STUDIO_API_BASE", "http://127.0.0.1:7899")


def _client(args: argparse.Namespace) -> ProcessorClient:
    return ProcessorClient(args.api_base, timeout=args.timeout)


def _json_mode(args: argparse.Namespace) -> bool:
    return not args.pretty


def cmd_health(args: argparse.Namespace) -> None:
    data = _client(args).health()
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_upload(args: argparse.Namespace) -> None:
    path = Path(args.file)
    data = _client(args).upload(path)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_create(args: argparse.Namespace) -> None:
    data = _client(args).workflow_create(args.file_id, name=args.name)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_get(args: argparse.Namespace) -> None:
    data = _client(args).workflow_get(args.workflow_id)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_list(args: argparse.Namespace) -> None:
    data = _client(args).workflow_list(args.page, args.page_size)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_results(args: argparse.Namespace) -> None:
    client = _client(args)
    data = client.workflow_results(args.workflow_id)
    saved: list[dict[str, Any]] = []
    if args.save_dir:
        out_dir = Path(args.save_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in data.get("files", []):
            fid = f["file_id"]
            name = f.get("name", fid)
            dest = out_dir / name
            dest.write_bytes(client.download_result_file(f))
            saved.append({"file_id": fid, "path": str(dest.resolve()), **f})
        emit(
            {"ok": True, "workflow_id": args.workflow_id, "files": saved or data.get("files", [])},
            json_mode=_json_mode(args),
        )
    else:
        emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_logs(args: argparse.Namespace) -> None:
    logs = _client(args).workflow_logs(args.workflow_id)
    emit({"ok": True, "workflow_id": args.workflow_id, "logs": logs}, json_mode=_json_mode(args))


def cmd_workflow_wait(args: argparse.Namespace) -> None:
    client = _client(args)
    wf_id = args.workflow_id
    deadline = time.time() + args.timeout
    last: dict | None = None
    while time.time() < deadline:
        last = client.workflow_get(wf_id)
        status = last.get("status")
        if status in ("completed", "failed"):
            ok = status == "completed"
            emit(
                {"ok": ok, "workflow_id": wf_id, "status": status, "workflow": last},
                json_mode=_json_mode(args),
            )
            raise SystemExit(0 if ok else 2)
        time.sleep(args.interval)
    emit_error(
        f"workflow {wf_id} did not finish within {args.timeout}s",
        code=2,
        detail=last,
        json_mode=_json_mode(args),
    )


def cmd_workflow_run(args: argparse.Namespace) -> None:
    """Upload file, create workflow, optionally wait and save artifacts."""
    client = _client(args)
    path = Path(args.file)
    up = client.upload(path)
    file_id = up["file_id"]
    wf = client.workflow_create(file_id, name=args.name)
    wf_id = wf["workflow_id"]
    result: dict[str, Any] = {
        "ok": True,
        "file_id": file_id,
        "workflow_id": wf_id,
        "upload": up,
        "workflow": wf,
    }
    if not args.wait:
        emit(result, json_mode=_json_mode(args))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        detail = client.workflow_get(wf_id)
        result["workflow"] = detail
        if detail.get("status") in ("completed", "failed"):
            break
        time.sleep(args.interval)
    status = result["workflow"].get("status")
    if status not in ("completed", "failed"):
        emit_error(
            f"workflow {wf_id} timed out after {args.timeout}s",
            code=2,
            detail=result["workflow"],
            json_mode=_json_mode(args),
        )
    results = client.workflow_results(wf_id)
    result["results"] = results
    if args.save_dir and status == "completed":
        out_dir = Path(args.save_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for f in results.get("files", []):
            dest = out_dir / f.get("name", f["file_id"])
            dest.write_bytes(client.download_result_file(f))
            saved.append({"path": str(dest.resolve()), **f})
        result["saved_files"] = saved
    result["ok"] = status == "completed"
    emit(result, json_mode=_json_mode(args))
    if status != "completed":
        raise SystemExit(2)


def cmd_file_download(args: argparse.Namespace) -> None:
    client = _client(args)
    data = client.file_download(
        args.file_id,
        download_url=args.url,
        step_type=args.step_type,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    emit(
        {"ok": True, "file_id": args.file_id, "path": str(out.resolve()), "size_bytes": len(data)},
        json_mode=_json_mode(args),
    )


def cmd_file_cat(args: argparse.Namespace) -> None:
    text = _client(args).file_text(
        args.file_id,
        download_url=args.url,
        step_type=args.step_type,
    )
    if _json_mode(args):
        emit({"ok": True, "file_id": args.file_id, "text": text}, json_mode=True)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def cmd_step_retry(args: argparse.Namespace) -> None:
    data = _client(args).step_retry(args.step_id)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_step_cancel(args: argparse.Namespace) -> None:
    data = _client(args).step_cancel(args.step_id)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_delete(args: argparse.Namespace) -> None:
    data = _client(args).workflow_delete(args.workflow_id, force=args.force)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_batch_delete(args: argparse.Namespace) -> None:
    data = _client(args).workflows_batch_delete(args.workflow_ids, force=args.force)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_artifacts_list(args: argparse.Namespace) -> None:
    data = _client(args).artifacts_list(
        args.page, args.page_size, step_type=args.step_type or None
    )
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_artifacts_batch_download(args: argparse.Namespace) -> None:
    data = _client(args).artifacts_batch_download(args.file_ids)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    emit(
        {"ok": True, "path": str(out.resolve()), "size_bytes": len(data), "count": len(args.file_ids)},
        json_mode=_json_mode(args),
    )


def cmd_workflow_pause(args: argparse.Namespace) -> None:
    data = _client(args).workflow_pause(args.workflow_id)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_resume(args: argparse.Namespace) -> None:
    data = _client(args).workflow_resume(args.workflow_id)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_batch_pause(args: argparse.Namespace) -> None:
    data = _client(args).workflows_batch_pause(args.workflow_ids)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_batch_resume(args: argparse.Namespace) -> None:
    data = _client(args).workflows_batch_resume(args.workflow_ids)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_queue_pause_lane(args: argparse.Namespace) -> None:
    data = _client(args).queue_pause_lane(args.lane)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_queue_resume_lane(args: argparse.Namespace) -> None:
    data = _client(args).queue_resume_lane(args.lane)
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_queue_pause_all(args: argparse.Namespace) -> None:
    data = _client(args).queue_pause_all()
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_queue_resume_all(args: argparse.Namespace) -> None:
    data = _client(args).queue_resume_all()
    emit({"ok": True, **data}, json_mode=_json_mode(args))


def cmd_workflow_batch_export(args: argparse.Namespace) -> None:
    data = _client(args).workflows_batch_export(args.workflow_ids)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    emit(
        {"ok": True, "path": str(out.resolve()), "size_bytes": len(data)},
        json_mode=_json_mode(args),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="processor",
        description="CLI for media-studio API (JSON output by default, for AI/scripts)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--api-base",
        default=DEFAULT_API,
        help=f"API base URL (env: MEDIA_STUDIO_API_BASE, default: {DEFAULT_API})",
    )
    p.add_argument("--timeout", type=float, default=600.0, help="HTTP timeout seconds")
    p.add_argument("--pretty", action="store_true", help="Human-readable output instead of JSON")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Check API health").set_defaults(func=cmd_health)

    up = sub.add_parser("upload", help="Upload a file")
    up.add_argument("file", help="Path to video/audio/markdown file")
    up.set_defaults(func=cmd_upload)

    wf = sub.add_parser("workflow", help="Workflow operations")
    wf_sub = wf.add_subparsers(dest="workflow_cmd", required=True)

    wcreate = wf_sub.add_parser("create", help="Create workflow for uploaded file")
    wcreate.add_argument("--file-id", required=True)
    wcreate.add_argument("--name", default=None)
    wcreate.set_defaults(func=cmd_workflow_create)

    wget = wf_sub.add_parser("get", help="Get workflow detail")
    wget.add_argument("workflow_id")
    wget.set_defaults(func=cmd_workflow_get)

    wlist = wf_sub.add_parser("list", help="List workflows")
    wlist.add_argument("--page", type=int, default=1)
    wlist.add_argument("--page-size", type=int, default=100)
    wlist.set_defaults(func=cmd_workflow_list)

    wres = wf_sub.add_parser("results", help="List completed artifact files")
    wres.add_argument("workflow_id")
    wres.add_argument("--save-dir", default=None, help="Download all artifacts to directory")
    wres.set_defaults(func=cmd_workflow_results)

    wlog = wf_sub.add_parser("logs", help="Execution logs for workflow")
    wlog.add_argument("workflow_id")
    wlog.set_defaults(func=cmd_workflow_logs)

    wwait = wf_sub.add_parser("wait", help="Poll until workflow completes or fails")
    wwait.add_argument("workflow_id")
    wwait.add_argument("--timeout", type=int, default=3600)
    wwait.add_argument("--interval", type=float, default=3.0)
    wwait.set_defaults(func=cmd_workflow_wait)

    wrun = wf_sub.add_parser("run", help="Upload + create workflow (+ optional wait)")
    wrun.add_argument("file", help="Path to input file")
    wrun.add_argument("--name", default=None)
    wrun.add_argument("--wait", action="store_true", help="Wait until workflow finishes")
    wrun.add_argument("--timeout", type=int, default=3600)
    wrun.add_argument("--interval", type=float, default=3.0)
    wrun.add_argument("--save-dir", default=None, help="With --wait: save artifacts here")
    wrun.set_defaults(func=cmd_workflow_run)

    wdel = wf_sub.add_parser("delete", help="Delete workflow and orphan files")
    wdel.add_argument("workflow_id")
    wdel.add_argument("--force", action="store_true")
    wdel.set_defaults(func=cmd_workflow_delete)

    wbdel = wf_sub.add_parser("batch-delete", help="Delete multiple workflows")
    wbdel.add_argument("workflow_ids", nargs="+")
    wbdel.add_argument("--force", action="store_true")
    wbdel.set_defaults(func=cmd_workflow_batch_delete)

    wexport = wf_sub.add_parser("batch-export", help="Export workflows as zip")
    wexport.add_argument("workflow_ids", nargs="+")
    wexport.add_argument("-o", "--output", required=True)
    wexport.set_defaults(func=cmd_workflow_batch_export)

    wpause = wf_sub.add_parser("pause", help="Pause workflow (stop scheduling)")
    wpause.add_argument("workflow_id")
    wpause.set_defaults(func=cmd_workflow_pause)

    wresume = wf_sub.add_parser("resume", help="Resume paused workflow")
    wresume.add_argument("workflow_id")
    wresume.set_defaults(func=cmd_workflow_resume)

    wbpause = wf_sub.add_parser("batch-pause", help="Pause multiple workflows")
    wbpause.add_argument("workflow_ids", nargs="+")
    wbpause.set_defaults(func=cmd_workflow_batch_pause)

    wbresume = wf_sub.add_parser("batch-resume", help="Resume multiple workflows")
    wbresume.add_argument("workflow_ids", nargs="+")
    wbresume.set_defaults(func=cmd_workflow_batch_resume)

    q = sub.add_parser("queue", help="Global queue lane control")
    q_sub = q.add_subparsers(dest="queue_cmd", required=True)

    queue_lanes = (
        "extract",
        "transcribe",
        "transcribe_fast",
        "transcribe_slow",
        "transcribe_external",
        "polish",
    )
    for lane in queue_lanes:
        qp = q_sub.add_parser(f"pause-{lane}", help=f"Pause {lane} lane")
        qp.set_defaults(func=cmd_queue_pause_lane, lane=lane)
        qr = q_sub.add_parser(f"resume-{lane}", help=f"Resume {lane} lane")
        qr.set_defaults(func=cmd_queue_resume_lane, lane=lane)

    q_sub.add_parser("pause-all", help="Pause all lanes").set_defaults(func=cmd_queue_pause_all)
    q_sub.add_parser("resume-all", help="Resume all lanes").set_defaults(func=cmd_queue_resume_all)

    fp = sub.add_parser("file", help="File operations")
    fp_sub = fp.add_subparsers(dest="file_cmd", required=True)

    def _file_fetch_opts(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--url",
            default=None,
            help="Download path from workflow results (e.g. /audio/<id>)",
        )
        parser.add_argument(
            "--step-type",
            default=None,
            choices=("extract_audio", "transcribe", "polish"),
            help="Infer legacy URL when /files/ is unavailable",
        )

    fdl = fp_sub.add_parser("download", help="Download file by id")
    fdl.add_argument("file_id")
    fdl.add_argument("-o", "--output", required=True)
    _file_fetch_opts(fdl)
    fdl.set_defaults(func=cmd_file_download)

    fcat = fp_sub.add_parser("cat", help="Print text file content (transcript/polish)")
    fcat.add_argument("file_id")
    _file_fetch_opts(fcat)
    fcat.set_defaults(func=cmd_file_cat)

    st = sub.add_parser("step", help="Step operations")
    st_sub = st.add_subparsers(dest="step_cmd", required=True)

    sretry = st_sub.add_parser("retry", help="Retry failed step")
    sretry.add_argument("step_id")
    sretry.set_defaults(func=cmd_step_retry)

    scancel = st_sub.add_parser("cancel", help="Cancel processing step")
    scancel.add_argument("step_id")
    scancel.set_defaults(func=cmd_step_cancel)

    art = sub.add_parser("artifacts", help="Global artifact (output) files")
    art_sub = art.add_subparsers(dest="artifacts_cmd", required=True)

    alist = art_sub.add_parser("list", help="List completed step outputs")
    alist.add_argument("--page", type=int, default=1)
    alist.add_argument("--page-size", type=int, default=100)
    alist.add_argument(
        "--step-type",
        default=None,
        choices=("extract_audio", "transcribe", "polish"),
    )
    alist.set_defaults(func=cmd_artifacts_list)

    adl = art_sub.add_parser("batch-download", help="Download selected artifacts as zip")
    adl.add_argument("file_ids", nargs="+")
    adl.add_argument("-o", "--output", required=True)
    adl.set_defaults(func=cmd_artifacts_batch_download)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ProcessorAPIError as e:
        emit_error(str(e), code=1, detail={"status_code": e.status_code, "body": e.body[:2000]}, json_mode=_json_mode(args))
    except FileNotFoundError as e:
        emit_error(str(e), code=1, json_mode=_json_mode(args))
    except KeyboardInterrupt:
        emit_error("interrupted", code=130, json_mode=_json_mode(args))


if __name__ == "__main__":
    main()
