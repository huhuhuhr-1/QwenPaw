import asyncio
import uuid
from functools import partial
from pathlib import Path
from datetime import datetime, timezone

from app.config import settings
from app.services.pipeline.queue_control import QueueController
from app.services.shared.storage import db, storage
from app.services.media.audio import audio_service, ProcessingError
from app.services.transcribe.service import transcribe_service
from app.services.polish.service import polish_service
from app.services.artifacts.run_info import format_step_run_model
from app.services.transcribe.lane_config import resolve_transcribe_lane
from app.services.transcribe.lane_limiter import TranscribeLaneLimiter
from app.services.transcribe.lanes import (
    lane_to_scheduler_queue,
    normalize_transcribe_lane,
    scheduler_queue_to_lane,
)
from app.services.transcribe.pool import transcribe_pool_size


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_SCHEDULER_CONCURRENCY: dict[str, str] = {
    "extract_audio": "max_concurrent_extract",
    "polish": "max_concurrent_polish",
}

_TRANSCRIBE_TIMEOUT: dict[str, str] = {
    "transcribe_fast": "timeout_transcribe_fast",
    "transcribe_slow": "timeout_transcribe_slow",
    "transcribe_external": "timeout_transcribe_external",
}

TRANSCRIBE_SCHEDULER_LANE = "transcribe"


def _scheduler_lane_for_step(step: dict, workflow: dict | None) -> str:
    if step["step_type"] == "transcribe":
        return TRANSCRIBE_SCHEDULER_LANE
    return step["step_type"]


def _transcribe_lane_pause_key(workflow: dict | None) -> str:
    lane = (workflow or {}).get("transcribe_lane") or "fast"
    return lane_to_scheduler_queue(lane)


class Scheduler:
    """FIFO per lane; all transcribe jobs share one competitive worker pool."""

    def __init__(self):
        self._queues: dict[str, asyncio.PriorityQueue] = {
            "extract_audio": asyncio.PriorityQueue(),
            TRANSCRIBE_SCHEDULER_LANE: asyncio.PriorityQueue(),
            "polish": asyncio.PriorityQueue(),
        }
        self._workers_started = False
        self._transcribe_workers = 0
        self._transcribe_limiter = TranscribeLaneLimiter()

    def ensure_workers(self) -> None:
        if self._workers_started:
            return
        self._workers_started = True
        for scheduler_lane, setting_name in _SCHEDULER_CONCURRENCY.items():
            n = max(1, getattr(settings, setting_name))
            queue = self._queues[scheduler_lane]
            for _ in range(n):
                asyncio.create_task(self._worker_loop(queue, scheduler_lane))
        self._spawn_transcribe_workers(transcribe_pool_size())

    def apply_config_reload(self) -> None:
        """Grow transcribe pool after settings save (shrink needs process restart)."""
        if not self._workers_started:
            return
        target = transcribe_pool_size()
        if target > self._transcribe_workers:
            self._spawn_transcribe_workers(target - self._transcribe_workers)

    def _spawn_transcribe_workers(self, count: int) -> None:
        if count <= 0:
            return
        queue = self._queues[TRANSCRIBE_SCHEDULER_LANE]
        for _ in range(count):
            asyncio.create_task(self._worker_loop(queue, TRANSCRIBE_SCHEDULER_LANE))
        self._transcribe_workers += count

    def schedule(self, step: dict, workflow_created_at: str, workflow: dict | None = None) -> None:
        self.ensure_workers()
        scheduler_lane = _scheduler_lane_for_step(step, workflow)
        queue = self._queues.get(scheduler_lane)
        if queue is None:
            raise ValueError(f"unknown scheduler lane: {scheduler_lane}")
        if scheduler_lane == TRANSCRIBE_SCHEDULER_LANE:
            lane = normalize_transcribe_lane((workflow or {}).get("transcribe_lane"))
            lane_rank = {"fast": 0, "slow": 1, "external": 2}.get(lane, 1)
            priority = (lane_rank, workflow_created_at, step["id"])
        else:
            priority = (0, workflow_created_at, step["id"])
        queue.put_nowait((priority, step, workflow))

    def queue_sizes(self) -> dict[str, int]:
        sizes = {lane: q.qsize() for lane, q in self._queues.items()}
        pool = sizes.get(TRANSCRIBE_SCHEDULER_LANE, 0)
        sizes["transcribe_fast"] = pool
        sizes["transcribe_slow"] = pool
        sizes["transcribe_external"] = pool
        return sizes

    async def _worker_loop(self, queue: asyncio.PriorityQueue, scheduler_lane: str) -> None:
        while True:
            _, step, workflow = await queue.get()
            try:
                wf = workflow or await db.get_workflow(step["workflow_id"])
                while self._is_worker_paused(scheduler_lane, wf):
                    await asyncio.sleep(0.5)
                    wf = workflow or await db.get_workflow(step["workflow_id"])
                if wf and wf.get("status") == "paused":
                    continue
                await self._run_step(step, scheduler_lane, wf)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception(
                    "worker %s failed for step %s: %s",
                    scheduler_lane,
                    step.get("id"),
                    exc,
                )
            finally:
                queue.task_done()

    @staticmethod
    def _is_worker_paused(scheduler_lane: str, workflow: dict | None) -> bool:
        if QueueController.is_paused(scheduler_lane):
            return True
        if scheduler_lane == TRANSCRIBE_SCHEDULER_LANE:
            return QueueController.is_paused(_transcribe_lane_pause_key(workflow))
        return False

    async def _run_step(self, step: dict, scheduler_lane: str, workflow: dict | None):
        step_id = step["id"]
        wf_id = step["workflow_id"]
        step_type = step["step_type"]

        timeout = self._get_timeout(scheduler_lane, step_type, workflow)

        run_model: str | None = None
        lane_acquired: str | None = None
        transcribe_lane_override: str | None = None
        try:
            if step_type == "transcribe":
                wf = workflow or await db.get_workflow(wf_id)
                bound = (wf or {}).get("transcribe_lane")
                lane_acquired = await self._transcribe_limiter.acquire(bound)
                transcribe_lane_override = lane_acquired
                bound_norm = normalize_transcribe_lane(bound) if bound else None
                if bound_norm != transcribe_lane_override:
                    await db.update_workflow_transcribe_lane(
                        wf_id, transcribe_lane_override
                    )
                    await db.add_log(
                        step_id,
                        "INFO",
                        f"transcribe_lane rerouted: {bound or '—'} -> "
                        f"{transcribe_lane_override} (执行时选路)",
                    )
                    workflow = await db.get_workflow(wf_id)

            await db.update_step(step_id, status="processing", started_at=now_ts())
            await db.add_log(
                step_id, "INFO", f"step started: {step_type} [{scheduler_lane}]"
            )

            coro = self._execute(step, workflow, transcribe_lane=transcribe_lane_override)
            run_model = await asyncio.wait_for(coro, timeout=timeout)

            await db.update_step(
                step_id,
                status="completed",
                completed_at=now_ts(),
                run_model=run_model,
            )
            await db.add_log(step_id, "INFO", f"step completed: {step_type}")

            await DagEngine.on_step_complete(step_id, wf_id)

        except asyncio.TimeoutError:
            await db.update_step(
                step_id,
                status="failed",
                error=f"timed out after {timeout}s",
                completed_at=now_ts(),
            )
            await db.add_log(step_id, "ERROR", f"step timed out after {timeout}s")
            await DagEngine.on_step_fail(step_id, wf_id)

        except ProcessingError as e:
            await db.update_step(
                step_id, status="failed", error=e.message, completed_at=now_ts()
            )
            await db.add_log(step_id, "ERROR", f"step failed: {e.message}")
            await DagEngine.on_step_fail(step_id, wf_id)

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            await db.update_step(
                step_id, status="failed", error=err_msg, completed_at=now_ts()
            )
            await db.add_log(step_id, "ERROR", f"step failed: {err_msg}")
            await DagEngine.on_step_fail(step_id, wf_id)
        finally:
            if lane_acquired:
                await self._transcribe_limiter.release(lane_acquired)

    def _get_timeout(self, scheduler_lane: str, step_type: str, workflow: dict | None) -> int:
        if step_type == "transcribe":
            lane_key = _transcribe_lane_pause_key(workflow)
            setting = _TRANSCRIBE_TIMEOUT.get(lane_key, "timeout_transcribe_slow")
            return getattr(settings, setting, settings.timeout_transcribe)
        return {
            "extract_audio": settings.timeout_extract,
            "polish": settings.timeout_polish,
        }.get(step_type, 600)

    async def _execute(
        self,
        step: dict,
        workflow: dict | None,
        *,
        transcribe_lane: str | None = None,
    ) -> str | None:
        step_type = step["step_type"]
        transcribe_lane: str | None = transcribe_lane
        input_file_id = step["input_file_id"]
        step_id = step["id"]
        wf_id = step["workflow_id"]

        input_file = await db.get_file(input_file_id) if input_file_id else None
        if not input_file:
            raise ProcessingError(f"input file {input_file_id} not found")

        input_path_obj = await storage.get_path(input_file_id)
        input_path = str(input_path_obj)

        out_name = self._output_name(input_file["original_name"], step_type)
        out_id = uuid.uuid4().hex[:12]
        out_dir = Path(settings.data_dir) / "files" / out_id
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / out_name)

        loop = asyncio.get_event_loop()

        if step_type == "extract_audio":
            await db.add_log(step_id, "INFO", f"extracting audio: {input_path}")
            await audio_service.extract_audio(
                input_path, output_path, fmt="mp3", step_id=step_id
            )
        elif step_type == "transcribe":
            wf = workflow or await db.get_workflow(wf_id)
            lane = transcribe_lane or resolve_transcribe_lane(
                (wf or {}).get("transcribe_lane")
            )
            transcribe_lane = lane
            backend_kind = _lane_backend_label(lane)
            await db.add_log(
                step_id,
                "INFO",
                f"transcribing lane={lane} backend={backend_kind}: {input_path}",
            )
            text = await loop.run_in_executor(
                None,
                partial(transcribe_service.transcribe, input_path, "zh", lane=lane),
            )
            await db.add_log(step_id, "INFO", f"transcribe done, {len(text)} chars")
            Path(output_path).write_text(text, encoding="utf-8")
        elif step_type == "polish":
            text = Path(input_path).read_text(encoding="utf-8")
            await db.add_log(step_id, "INFO", f"polishing {len(text)} chars via MiniMax")
            result = await loop.run_in_executor(None, polish_service.polish, text)
            await db.add_log(step_id, "INFO", f"polish done, {len(result)} chars")
            Path(output_path).write_text(result, encoding="utf-8")

        file_size = Path(output_path).stat().st_size
        await db.create_file(
            out_id,
            self._output_type(step_type),
            out_name,
            str(out_dir / out_name),
            file_size,
        )
        await db.update_step(step_id, output_file_id=out_id)
        return format_step_run_model(step_type, lane=transcribe_lane)

    def _output_name(self, original_name: str, step_type: str) -> str:
        base = Path(original_name).stem
        return {
            "extract_audio": f"{base}.mp3",
            "transcribe": f"{base}.txt",
            "polish": f"{base}.polished.md",
        }.get(step_type, f"{base}.out")

    def _output_type(self, step_type: str) -> str:
        return {
            "extract_audio": "audio",
            "transcribe": "markdown",
            "polish": "markdown",
        }.get(step_type, "markdown")


def _lane_backend_label(lane: str) -> str:
    lane = normalize_transcribe_lane(lane)
    if lane == "fast":
        return settings.transcribe_fast_backend
    if lane == "slow":
        return settings.transcribe_slow_backend
    return settings.transcribe_external_backend


class DagEngine:
    scheduler = Scheduler()

    @classmethod
    def _enqueue_step(cls, step: dict, workflow_created_at: str, workflow: dict | None = None) -> None:
        if step["step_type"] == "transcribe":
            if QueueController.is_paused(TRANSCRIBE_SCHEDULER_LANE):
                return
            if QueueController.is_paused(_transcribe_lane_pause_key(workflow)):
                return
        else:
            scheduler_lane = _scheduler_lane_for_step(step, workflow)
            if QueueController.is_paused(scheduler_lane):
                return
        cls.scheduler.schedule(step, workflow_created_at, workflow)

    @classmethod
    async def _schedule_runnable_steps(
        cls,
        *,
        workflow_id: str | None = None,
        step_type: str | None = None,
        scheduler_lane: str | None = None,
    ) -> int:
        step_filter = step_type
        transcribe_lane_filter = None
        if scheduler_lane == TRANSCRIBE_SCHEDULER_LANE:
            step_filter = "transcribe"
        elif scheduler_lane and scheduler_lane.startswith("transcribe_"):
            step_filter = "transcribe"
            transcribe_lane_filter = scheduler_queue_to_lane(scheduler_lane)

        n = 0
        for step in await db.get_runnable_pending_steps(
            step_type=step_filter,
            workflow_id=workflow_id,
            transcribe_lane=transcribe_lane_filter,
        ):
            wf = await db.get_workflow(step["workflow_id"])
            if not wf or wf.get("status") != "processing":
                continue
            if step["step_type"] == "transcribe":
                if QueueController.is_paused(TRANSCRIBE_SCHEDULER_LANE):
                    continue
                if QueueController.is_paused(_transcribe_lane_pause_key(wf)):
                    continue
            else:
                lane = _scheduler_lane_for_step(step, wf)
                if QueueController.is_paused(lane):
                    continue
            cls.scheduler.schedule(step, wf.get("created_at", ""), wf)
            n += 1
        return n

    @classmethod
    async def pause_workflow(cls, workflow_id: str) -> int:
        wf = await db.get_workflow(workflow_id)
        if not wf:
            raise ValueError("workflow not found")
        if wf["status"] in ("completed", "failed"):
            raise ValueError("cannot pause finished workflow")
        if wf["status"] == "paused":
            return 0

        await db.update_workflow_status(workflow_id, "paused")
        await db.add_log(None, "INFO", f"workflow {workflow_id} paused by user")
        return 0

    @classmethod
    async def resume_workflow(cls, workflow_id: str) -> int:
        wf = await db.get_workflow(workflow_id)
        if not wf:
            raise ValueError("workflow not found")
        if wf["status"] not in ("paused", "pending", "processing"):
            raise ValueError("workflow cannot be resumed")

        await db.update_workflow_status(workflow_id, "processing")
        await db.add_log(None, "INFO", f"workflow {workflow_id} resumed by user")
        return await cls._schedule_runnable_steps(workflow_id=workflow_id)

    @classmethod
    async def pause_workflows_batch(cls, workflow_ids: list[str]) -> dict:
        updated, errors = [], []
        for wid in workflow_ids:
            try:
                await cls.pause_workflow(wid)
                updated.append(wid)
            except ValueError as e:
                errors.append({"workflow_id": wid, "error": str(e)})
        return {"updated": updated, "errors": errors}

    @classmethod
    async def resume_workflows_batch(cls, workflow_ids: list[str]) -> dict:
        updated, errors = [], []
        for wid in workflow_ids:
            try:
                await cls.resume_workflow(wid)
                updated.append(wid)
            except ValueError as e:
                errors.append({"workflow_id": wid, "error": str(e)})
        return {"updated": updated, "errors": errors}

    @classmethod
    async def create_workflow(
        cls,
        file_id: str,
        entry_type: str,
        name: str | None = None,
    ) -> dict:
        try:
            lane = resolve_transcribe_lane(None)
        except ValueError as e:
            raise ValueError(str(e)) from e
        wf_id = uuid.uuid4().hex[:12]
        wf = await db.create_workflow(
            wf_id, file_id, entry_type, name, transcribe_lane=lane
        )
        await db.add_log(
            None,
            "INFO",
            f"workflow {wf_id} auto-routed transcribe_lane={lane}",
        )
        wf_created = wf.get("created_at", "")

        input_file = await db.get_file(file_id)
        if not input_file:
            raise ValueError(f"file {file_id} not found")

        dag = cls._build_dag(entry_type, wf_id, file_id)
        for step_data in dag:
            step = await db.create_step(**step_data)
            await db.add_log(step["id"], "INFO", f"step created: {step['step_type']}")

        steps = await db.get_workflow_steps(wf_id)
        await db.update_workflow_status(wf_id, "processing")

        wf_full = await db.get_workflow(wf_id)
        for s in steps:
            if s["status"] == "pending" and not s["depends_on"]:
                cls._enqueue_step(s, wf_created, wf_full)

        return await db.get_workflow(wf_id)

    @classmethod
    def _build_dag(cls, entry_type: str, workflow_id: str, entry_file_id: str) -> list[dict]:
        steps = []
        prev_id = None

        if entry_type == "video":
            sid = uuid.uuid4().hex[:12]
            steps.append(
                dict(
                    step_id=sid,
                    workflow_id=workflow_id,
                    step_type="extract_audio",
                    input_file_id=entry_file_id,
                    depends_on=None,
                )
            )
            prev_id = sid

        if entry_type in ("video", "audio"):
            sid = uuid.uuid4().hex[:12]
            steps.append(
                dict(
                    step_id=sid,
                    workflow_id=workflow_id,
                    step_type="transcribe",
                    input_file_id=entry_file_id if entry_type == "audio" else None,
                    depends_on=prev_id,
                )
            )
            prev_id = sid

        sid = uuid.uuid4().hex[:12]
        steps.append(
            dict(
                step_id=sid,
                workflow_id=workflow_id,
                step_type="polish",
                input_file_id=entry_file_id if entry_type == "markdown" else None,
                depends_on=prev_id,
            )
        )

        return steps

    @classmethod
    async def on_step_complete(cls, step_id: str, workflow_id: str):
        await db.add_log(step_id, "INFO", "step completed, checking dependents")
        next_steps = await db.get_pending_dependents(workflow_id, step_id)

        if not next_steps:
            steps = await db.get_workflow_steps(workflow_id)
            all_done = all(s["status"] in ("completed", "failed", "cancelled") for s in steps)
            all_ok = all(s["status"] == "completed" for s in steps)
            if all_done:
                await db.update_workflow_status(
                    workflow_id, "completed" if all_ok else "failed"
                )
            return

        completed_step = await db.get_step(step_id)
        output_id = completed_step.get("output_file_id") if completed_step else None

        wf = await db.get_workflow(workflow_id)
        if wf and wf.get("status") == "paused":
            return

        for ns in next_steps:
            if not ns["input_file_id"] and output_id:
                await db.update_step(ns["id"], input_file_id=output_id)
                ns["input_file_id"] = output_id

            await db.add_log(ns["id"], "INFO", "dependency met, scheduling")
            cls._enqueue_step(ns, wf.get("created_at", "") if wf else "", wf)

    @classmethod
    async def on_step_fail(cls, step_id: str, workflow_id: str):
        step = await db.get_step(step_id)
        step_type = step["step_type"] if step else "unknown"
        await db.add_log(step_id, "ERROR", f"{step_type} failed")
        await db.update_workflow_status(workflow_id, "failed")

    @classmethod
    async def on_step_cancelled(cls, step_id: str, workflow_id: str):
        next_steps = await db.get_steps_by_depends_on(workflow_id, step_id)
        for ns in next_steps:
            if ns["status"] == "pending":
                await db.update_step(
                    ns["id"],
                    status="cancelled",
                    error=f"upstream {step_id} cancelled",
                )
                await db.add_log(ns["id"], "INFO", f"cascade cancelled by {step_id}")
                await cls.on_step_cancelled(ns["id"], workflow_id)

    @classmethod
    async def retry_step(cls, step_id: str) -> int:
        step = await db.get_step(step_id)
        if not step:
            raise ValueError("step not found")
        if step["status"] != "failed":
            raise ValueError("only failed steps can be retried")

        await db.update_step(
            step_id,
            status="pending",
            error=None,
            started_at=None,
            completed_at=None,
        )
        await db.add_log(step_id, "INFO", "step retried by user")

        count = await cls._cascade_reset(step["workflow_id"], step_id)

        if not step["depends_on"]:
            updated = await db.get_step(step_id)
            wf = await db.get_workflow(step["workflow_id"])
            cls._enqueue_step(updated, wf.get("created_at", "") if wf else "", wf)

        return 1 + count

    @classmethod
    async def _cascade_reset(cls, workflow_id: str, step_id: str) -> int:
        count = 0
        dependents = await db.get_steps_by_depends_on(workflow_id, step_id)
        for dep in dependents:
            if dep["status"] == "failed":
                await db.update_step(
                    dep["id"],
                    status="pending",
                    error=None,
                    started_at=None,
                    completed_at=None,
                )
                await db.add_log(dep["id"], "INFO", "cascade reset by retry")
                count += 1
                count += await cls._cascade_reset(workflow_id, dep["id"])
        return count

    @classmethod
    async def cancel_step(cls, step_id: str) -> int:
        step = await db.get_step(step_id)
        if not step:
            raise ValueError("step not found")
        if step["status"] != "processing":
            raise ValueError("only processing steps can be cancelled")

        await db.update_step(
            step_id,
            status="cancelled",
            completed_at=now_ts(),
            error="cancelled by user",
        )
        await db.add_log(step_id, "INFO", "step cancelled by user")

        await cls.on_step_cancelled(step_id, step["workflow_id"])

        cancelled = 1
        for s in await db.get_steps_by_depends_on(step["workflow_id"], step_id):
            if s["status"] == "cancelled":
                cancelled += 1
        return cancelled

    @classmethod
    async def recovery_scan(cls):
        orphaned = await db.get_steps_by_status("processing")
        for step in orphaned:
            await db.update_step(
                step["id"],
                status="failed",
                error="service restart - step interrupted",
                completed_at=now_ts(),
            )
            await db.add_log(step["id"], "WARN", "step interrupted by service restart")
            await cls.on_step_fail(step["id"], step["workflow_id"])

        workflows = await db.get_active_workflows()
        for wf in workflows:
            steps = await db.get_workflow_steps(wf["id"])
            for s in steps:
                if s["status"] == "pending":
                    wf_created = wf.get("created_at", "")
                    if not s["depends_on"]:
                        await db.add_log(s["id"], "INFO", "re-scheduled after restart")
                        cls._enqueue_step(s, wf_created, wf)
                    else:
                        dep = await db.get_step(s["depends_on"])
                        if dep and dep["status"] == "completed":
                            await db.add_log(s["id"], "INFO", "re-scheduled after restart")
                            cls._enqueue_step(s, wf_created, wf)
