from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Literal


S3_FILES = ("data.json", "surrogate.json", "next_x.json")
S3Status = Literal["missing", "pending", "persisted", "failed"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def measurement_to_points(measurement: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not measurement:
        return []
    dataset_x = measurement.get("dataset_x")
    dataset_y = measurement.get("dataset_y")
    if not isinstance(dataset_x, list) or not isinstance(dataset_y, list):
        return []

    points: list[dict[str, Any]] = []
    for coords, value in zip(dataset_x, dataset_y):
        if not isinstance(coords, list) or len(coords) < 2:
            continue
        points.append(
            {
                "labx": coords[0],
                "labz": coords[1],
                "center_value": value,
            }
        )
    return points


def flatten_next_points(next_x: list[dict[str, Any]] | None) -> dict[str, Any]:
    all_points: list[dict[str, Any]] = []
    if not isinstance(next_x, list):
        return {"all": all_points, "latest": None}

    for workflow in next_x:
        if not isinstance(workflow, dict):
            continue
        workflow_id = str(workflow.get("workflow_id", ""))
        data = workflow.get("data")
        if not isinstance(data, list):
            continue
        for idx, coords in enumerate(data, start=1):
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            all_points.append(
                {
                    "workflow_id": workflow_id,
                    "labx": coords[0],
                    "labz": coords[1],
                    "sequence": idx,
                }
            )

    return {"all": all_points, "latest": all_points[-1] if all_points else None}


class LiveStateStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {
            "revision": 0,
            "measurement_revision": 0,
            "surrogate_revision": 0,
            "next_x_revision": 0,
            "measurement": None,
            "surrogate": None,
            "next_x": [],
            "measured_points": [],
            "next_points": {"all": [], "latest": None},
            "s3": {
                name: {
                    "status": "missing",
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "error": None,
                }
                for name in S3_FILES
            },
            "updated_at": utc_now(),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def load_initial(
        self,
        *,
        measurement: dict[str, Any] | None = None,
        surrogate: dict[str, Any] | None = None,
        next_x: list[dict[str, Any]] | None = None,
    ) -> None:
        if measurement is None and surrogate is None and next_x is None:
            return

        with self._lock:
            if measurement is not None:
                self._state["measurement"] = copy.deepcopy(measurement)
                self._state["measured_points"] = measurement_to_points(measurement)
            if surrogate is not None:
                self._state["surrogate"] = copy.deepcopy(surrogate)
            if next_x is not None:
                copied = copy.deepcopy(next_x)
                self._state["next_x"] = copied
                self._state["next_points"] = flatten_next_points(copied)

            for file_name, value in (
                ("data.json", measurement),
                ("surrogate.json", surrogate),
                ("next_x.json", next_x),
            ):
                if value is not None:
                    self._state["s3"][file_name]["status"] = "persisted"
                    self._state["s3"][file_name]["last_success_at"] = utc_now()

            self._bump_locked()

    def update_measurement(self, measurement: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._state["measurement"] = copy.deepcopy(measurement)
            self._state["measured_points"] = measurement_to_points(measurement)
            self._state["measurement_revision"] += 1
            self._bump_locked()
            return copy.deepcopy(self._state)

    def update_surrogate(self, surrogate: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._state["surrogate"] = copy.deepcopy(surrogate)
            self._state["surrogate_revision"] += 1
            self._bump_locked()
            return copy.deepcopy(self._state)

    def update_next_x(self, next_x: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            copied = copy.deepcopy(next_x)
            self._state["next_x"] = copied
            self._state["next_points"] = flatten_next_points(copied)
            self._state["next_x_revision"] += 1
            self._bump_locked()
            return copy.deepcopy(self._state)

    def update_s3_status(
        self,
        file_name: str,
        status: S3Status,
        *,
        error: str | None = None,
    ) -> dict[str, Any]:
        if file_name not in S3_FILES:
            raise ValueError(f"Unsupported S3 status file: {file_name}")

        now = utc_now()
        with self._lock:
            entry = self._state["s3"][file_name]
            entry["status"] = status
            entry["error"] = error
            if status in ("pending", "failed"):
                entry["last_attempt_at"] = now
            if status == "persisted":
                entry["last_success_at"] = now
                entry["error"] = None
            self._bump_locked()
            return copy.deepcopy(self._state)

    def meta(self) -> dict[str, Any]:
        state = self.snapshot()
        return {
            "revision": state["revision"],
            "measurement_revision": state["measurement_revision"],
            "surrogate_revision": state["surrogate_revision"],
            "next_x_revision": state["next_x_revision"],
            "s3": state["s3"],
            "updated_at": state["updated_at"],
        }

    def _bump_locked(self) -> None:
        self._state["revision"] += 1
        self._state["updated_at"] = utc_now()
