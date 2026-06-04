from __future__ import annotations

import asyncio
import copy
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomic_io import write_json_atomic
from .live_state import LiveStateStore, utc_now
from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


@dataclass
class UploadJob:
    file_name: str
    attempts: int = 0
    status: str = "pending"
    last_error: str | None = None
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "attempts": self.attempts,
            "status": self.status,
            "last_error": self.last_error,
            "updated_at": self.updated_at or utc_now(),
        }


class UploadOutbox:
    def __init__(
        self,
        *,
        data_dir: Path,
        uploader: Any,
        live_state: LiveStateStore,
        websocket_manager: WebSocketManager | None = None,
        retry_interval_seconds: float = 5.0,
        max_retry_interval_seconds: float = 60.0,
    ) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "upload_outbox.json"
        self.uploader = uploader
        self.live_state = live_state
        self.websocket_manager = websocket_manager
        self.retry_interval_seconds = retry_interval_seconds
        self.max_retry_interval_seconds = max_retry_interval_seconds
        self._lock = asyncio.Lock()
        self._thread_lock = threading.RLock()
        self._wakeup: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False
        self._jobs: dict[str, dict[str, Any]] = {}
        self._load()

    def enqueue_sync(self, file_name: str) -> None:
        with self._thread_lock:
            job = UploadJob(file_name=file_name, updated_at=utc_now()).as_dict()
            existing = self._jobs.get(file_name, {})
            job["attempts"] = int(existing.get("attempts", 0))
            self._jobs[file_name] = job
            self._persist()
        state = self.live_state.update_s3_status(file_name, "pending")
        self._publish("s3_status_updated", state)
        self._wake()

    async def enqueue(self, file_name: str) -> None:
        async with self._lock:
            self.enqueue_sync(file_name)

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._wakeup = asyncio.Event()
        while not self._closed:
            await self.process_once()
            try:
                await asyncio.wait_for(
                    self._wakeup.wait(),
                    timeout=self.retry_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
            self._wakeup.clear()

    async def process_once(self) -> bool:
        async with self._lock:
            with self._thread_lock:
                pending = [
                    copy.deepcopy(job)
                    for job in self._jobs.values()
                    if job.get("status") in ("pending", "failed")
                ]
        if not pending:
            return False

        for job in pending:
            file_name = str(job["file_name"])
            try:
                await asyncio.to_thread(self.uploader.upload_file, file_name)
            except Exception as exc:
                logger.exception("Failed to upload %s from outbox", file_name)
                await self._mark_failed(file_name, str(exc))
            else:
                await self._mark_persisted(file_name)
        return True

    async def _mark_failed(self, file_name: str, error: str) -> None:
        async with self._lock:
            with self._thread_lock:
                job = self._jobs.setdefault(file_name, UploadJob(file_name=file_name).as_dict())
                job["attempts"] = int(job.get("attempts", 0)) + 1
                job["status"] = "failed"
                job["last_error"] = error
                job["updated_at"] = utc_now()
                self._persist()
        state = self.live_state.update_s3_status(file_name, "failed", error=error)
        self._publish("s3_status_updated", state)

    async def _mark_persisted(self, file_name: str) -> None:
        async with self._lock:
            with self._thread_lock:
                self._jobs.pop(file_name, None)
                self._persist()
        state = self.live_state.update_s3_status(file_name, "persisted")
        self._publish("s3_status_updated", state)

    def stop(self) -> None:
        self._closed = True
        self._wake()

    def jobs_snapshot(self) -> list[dict[str, Any]]:
        with self._thread_lock:
            return copy.deepcopy(list(self._jobs.values()))

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            import json

            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Ignoring corrupt upload outbox: %s", self.path, exc_info=True)
            return
        if isinstance(raw, list):
            with self._thread_lock:
                self._jobs = {
                    str(job.get("file_name")): job
                    for job in raw
                    if isinstance(job, dict) and job.get("file_name")
                }

    def _persist(self) -> None:
        write_json_atomic(self.path, list(self._jobs.values()))

    def _publish(self, event_type: str, state: dict[str, Any]) -> None:
        if self.websocket_manager is not None:
            self.websocket_manager.publish(event_type, state)

    def _wake(self) -> None:
        if self._wakeup is not None:
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._wakeup.set)
            else:
                self._wakeup.set()
