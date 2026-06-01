"""HTTP client for the media-studio REST API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class ProcessorAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


_STEP_DOWNLOAD_PREFIX = {
    "extract_audio": "/audio/",
    "transcribe": "/document/",
    "polish": "/polished/",
}


class ProcessorClient:
    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        files: dict | None = None,
        expect_json: bool = True,
    ) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.request(method, self._url(path), json=json, files=files)
        if resp.status_code >= 400:
            raise ProcessorAPIError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                body=resp.text,
            )
        if not expect_json:
            return resp.content
        if not resp.content:
            return {}
        ct = resp.headers.get("content-type", "")
        if "application/json" in ct:
            return resp.json()
        return {"raw": resp.text}

    def health(self) -> dict:
        return self._request("GET", "/health")

    def upload(self, path: Path) -> dict:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        content = path.read_bytes()
        files = {"file": (path.name, content, "application/octet-stream")}
        return self._request("POST", "/upload", files=files)

    def workflow_create(self, file_id: str, name: str | None = None) -> dict:
        body: dict[str, Any] = {"file_id": file_id}
        if name:
            body["name"] = name
        return self._request("POST", "/workflows", json=body)

    def workflow_get(self, workflow_id: str) -> dict:
        return self._request("GET", f"/workflows/{workflow_id}")

    def workflow_list(self, page: int = 1, page_size: int = 100) -> dict:
        return self._request(
            "GET", f"/workflows?page={page}&page_size={page_size}"
        )

    def workflow_results(self, workflow_id: str) -> dict:
        return self._request("GET", f"/workflows/{workflow_id}/results")

    def workflow_logs(self, workflow_id: str) -> list:
        return self._request("GET", f"/workflows/{workflow_id}/logs")

    def step_retry(self, step_id: str) -> dict:
        return self._request("POST", f"/steps/{step_id}/retry")

    def step_cancel(self, step_id: str) -> dict:
        return self._request("POST", f"/steps/{step_id}/cancel")

    def workflow_delete(self, workflow_id: str, *, force: bool = False) -> dict:
        q = "?force=true" if force else ""
        return self._request("DELETE", f"/workflows/{workflow_id}{q}")

    def workflows_batch_delete(
        self, workflow_ids: list[str], *, force: bool = False
    ) -> dict:
        q = "?force=true" if force else ""
        return self._request(
            "POST", f"/workflows/batch-delete{q}", json={"workflow_ids": workflow_ids}
        )

    def workflows_batch_export(self, workflow_ids: list[str]) -> bytes:
        return self._request(
            "POST",
            "/workflows/batch-export",
            json={"workflow_ids": workflow_ids},
            expect_json=False,
        )

    def artifacts_list(
        self, page: int = 1, page_size: int = 100, step_type: str | None = None
    ) -> dict:
        q = f"page={page}&page_size={page_size}"
        if step_type:
            q += f"&step_type={step_type}"
        return self._request("GET", f"/artifacts?{q}")

    def workflow_pause(self, workflow_id: str) -> dict:
        return self._request("POST", f"/workflows/{workflow_id}/pause")

    def workflow_resume(self, workflow_id: str) -> dict:
        return self._request("POST", f"/workflows/{workflow_id}/resume")

    def workflows_batch_pause(self, workflow_ids: list[str]) -> dict:
        return self._request("POST", "/workflows/batch-pause", json={"workflow_ids": workflow_ids})

    def workflows_batch_resume(self, workflow_ids: list[str]) -> dict:
        return self._request("POST", "/workflows/batch-resume", json={"workflow_ids": workflow_ids})

    def queue_pause_lane(self, lane: str) -> dict:
        return self._request("POST", f"/queues/{lane}/pause")

    def queue_resume_lane(self, lane: str) -> dict:
        return self._request("POST", f"/queues/{lane}/resume")

    def queue_pause_all(self) -> dict:
        return self._request("POST", "/queues/pause-all")

    def queue_resume_all(self) -> dict:
        return self._request("POST", "/queues/resume-all")

    def artifacts_batch_download(self, file_ids: list[str]) -> bytes:
        return self._request(
            "POST",
            "/artifacts/batch-download",
            json={"file_ids": file_ids},
            expect_json=False,
        )

    def file_download(
        self,
        file_id: str,
        *,
        download_url: str | None = None,
        step_type: str | None = None,
        download: bool = True,
    ) -> bytes:
        """Download file bytes; tries unified /files/ then legacy step URLs."""
        candidates: list[str] = []
        if download_url:
            candidates.append(download_url)
        q = "?download=true" if download else ""
        candidates.append(f"/files/{file_id}{q}")
        if step_type:
            prefix = _STEP_DOWNLOAD_PREFIX.get(step_type)
            if prefix:
                candidates.append(f"{prefix}{file_id}")
        seen: set[str] = set()
        last_err: ProcessorAPIError | None = None
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            try:
                return self._request("GET", path, expect_json=False)
            except ProcessorAPIError as exc:
                if exc.status_code == 404:
                    last_err = exc
                    continue
                raise
        if last_err:
            raise last_err
        raise ProcessorAPIError(f"no download path for file {file_id}")

    def download_result_file(self, entry: dict) -> bytes:
        step = entry.get("step_type")
        if isinstance(step, dict):
            step = step.get("value") or step.get("name")
        return self.file_download(
            entry["file_id"],
            download_url=entry.get("download_url"),
            step_type=str(step) if step else None,
        )

    def file_text(
        self,
        file_id: str,
        *,
        download_url: str | None = None,
        step_type: str | None = None,
    ) -> str:
        data = self.file_download(
            file_id,
            download_url=download_url,
            step_type=step_type,
            download=False,
        )
        return data.decode("utf-8", errors="replace")
