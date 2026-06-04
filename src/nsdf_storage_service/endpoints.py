from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intersect_sdk import INTERSECT_RESPONSE_VALUE

from . import s3_uploader
from .atomic_io import write_json_atomic
from .data_models import NewMeasurementData, NextPointData, SurrogateValuesData
from .live_state import LiveStateStore
from .upload_outbox import UploadOutbox
from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


DATA_FILE = "data.json"
NEXT_X_FILE = "next_x.json"
SURROGATE_FILE = "surrogate.json"


class LiveUpdateSink:
    def __init__(
        self,
        *,
        live_state: LiveStateStore,
        upload_outbox: UploadOutbox,
        websocket_manager: WebSocketManager,
        data_dir: Path,
    ) -> None:
        self.live_state = live_state
        self.upload_outbox = upload_outbox
        self.websocket_manager = websocket_manager
        self.data_dir = data_dir

    def handle_measurement(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.data_dir / DATA_FILE, payload)
        state = self.live_state.update_measurement(payload)
        self.websocket_manager.publish("measurement_updated", state)
        self.upload_outbox.enqueue_sync(DATA_FILE)

    def handle_next_x(self, payload: list[dict[str, Any]]) -> None:
        write_json_atomic(self.data_dir / NEXT_X_FILE, payload)
        state = self.live_state.update_next_x(payload)
        self.websocket_manager.publish("next_point_updated", state)
        self.upload_outbox.enqueue_sync(NEXT_X_FILE)

    def handle_surrogate(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.data_dir / SURROGATE_FILE, payload)
        state = self.live_state.update_surrogate(payload)
        self.websocket_manager.publish("surrogate_updated", state)
        self.upload_outbox.enqueue_sync(SURROGATE_FILE)


class MeasurementAccumulator:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        live_sink: LiveUpdateSink | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._live_sink = live_sink

    def _normalize_payload(self, payload: INTERSECT_RESPONSE_VALUE) -> Any:
        """Validate and dump payload as a dict, warn on mismatch."""
        if isinstance(payload, dict):
            try:
                return NewMeasurementData.model_validate(payload).model_dump()
            except ValueError:
                logger.warning(
                    "Received new_measurement payload that does not match expected model"
                )
        return payload

    def _load_existing_snapshot(self) -> dict[str, Any]:
        data_file = (self._data_dir or s3_uploader.uploader_data_dir()) / DATA_FILE
        if data_file.exists():
            try:
                data = json.loads(data_file.read_text())
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                logger.warning("Existing data.json is corrupt; starting a new snapshot")

        return {
            "dataset_x": [],
            "dataset_y": [],
            "backend": "sklearn",
            "kernel": "rbf",
            "bounds": [[-47.33, 26.17], [-255.3, -242.3]],
            "y_is_good": True,
            "seed": -1,
            "dim_x": 2,
            "preprocess_log": False,
            "preprocess_standardize": False,
        }

    def _to_snapshot_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Snapshot payload already includes full dataset arrays.
        if isinstance(payload.get("dataset_x"), list) and isinstance(
            payload.get("dataset_y"), list
        ):
            return payload

        snapshot = self._load_existing_snapshot()
        dataset_x = snapshot.setdefault("dataset_x", [])
        dataset_y = snapshot.setdefault("dataset_y", [])

        if payload.get("next_x") is not None and payload.get("next_y") is not None:
            dataset_x.append(payload["next_x"])
            dataset_y.append(payload["next_y"])
        elif all(k in payload for k in ("labx", "labz", "center_value")):
            dataset_x.append([payload["labx"], payload["labz"]])
            dataset_y.append(payload["center_value"])
        else:
            logger.warning("new_measurement payload did not include snapshot or point fields")

        return snapshot

    def handle_new_measurement(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        """Write the latest workflow snapshot to data.json and upload to S3."""
        now = datetime.now(timezone.utc).isoformat()
        normalized_payload = self._normalize_payload(payload)

        logger.info(
            "time_utc=%s source=%s capability=%s endpoint=%s",
            now,
            source,
            capability_name,
            endpoint_name,
        )

        if isinstance(normalized_payload, dict):
            normalized_payload = self._to_snapshot_payload(normalized_payload)
            if self._live_sink is not None:
                self._live_sink.handle_measurement(normalized_payload)
            else:
                data_file = s3_uploader.uploader_data_dir() / DATA_FILE
                data_file.write_text(
                    json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n"
                )
                s3_uploader.upload_file(DATA_FILE)
        else:
            logger.warning("Unexpected payload type: %s", type(normalized_payload).__name__)


class DialResultStorage:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        live_sink: LiveUpdateSink | None = None,
    ) -> None:
        self._next_point_workflows: list[dict[str, Any]] = []
        self._next_points_initialized = False
        self._data_dir = data_dir
        self._live_sink = live_sink

    def _load_existing_next_points(self) -> None:
        if self._next_points_initialized:
            return

        output_file = (self._data_dir or s3_uploader.uploader_data_dir()) / NEXT_X_FILE
        if output_file.exists():
            try:
                data = json.loads(output_file.read_text())
                if isinstance(data, list):
                    self._next_point_workflows = data
                    logger.info(
                        "Restored %d next-point workflows from %s",
                        len(data),
                        output_file,
                    )
                else:
                    logger.warning(
                        "Existing %s has unexpected structure; starting fresh", NEXT_X_FILE
                    )
            except (json.JSONDecodeError, ValueError):
                logger.warning("Existing %s is corrupt; starting fresh", NEXT_X_FILE)

        self._next_points_initialized = True

    def _normalize_next_point(self, payload: INTERSECT_RESPONSE_VALUE) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            try:
                next_point = NextPointData.model_validate(payload)
                return {
                    "workflow_id": next_point.workflow_id,
                    "data": next_point.data,
                }
            except ValueError:
                logger.warning("Received next_point payload that does not match expected model")
                return None

        logger.warning("Unexpected next_point payload type: %s", type(payload).__name__)
        return None

    def _normalize_surrogate_values(
        self, payload: INTERSECT_RESPONSE_VALUE
    ) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            try:
                surrogate_values = SurrogateValuesData.model_validate(payload)
                normalized: dict[str, Any] = {
                    "workflow_id": surrogate_values.workflow_id,
                    "surrogate": surrogate_values.data[0],
                    "uncertainty": surrogate_values.data[1],
                }
                if len(surrogate_values.data) > 2:
                    normalized["raw_uncertainty"] = surrogate_values.data[2]
                return normalized
            except ValueError:
                logger.warning(
                    "Received surrogate_values payload that does not match expected model"
                )
                return None

        logger.warning("Unexpected surrogate_values payload type: %s", type(payload).__name__)
        return None

    def handle_next_point(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        logger.info(
            "time_utc=%s source=%s capability=%s endpoint=%s",
            now,
            source,
            capability_name,
            endpoint_name,
        )

        normalized_payload = self._normalize_next_point(payload)
        if normalized_payload is None:
            return

        self._load_existing_next_points()

        workflow_id = normalized_payload["workflow_id"]
        next_point = normalized_payload["data"]
        for workflow in self._next_point_workflows:
            if workflow.get("workflow_id") == workflow_id:
                workflow.setdefault("data", []).append(next_point)
                break
        else:
            self._next_point_workflows.append(
                {
                    "workflow_id": workflow_id,
                    "data": [next_point],
                }
            )

        if self._live_sink is not None:
            self._live_sink.handle_next_x(self._next_point_workflows)
        else:
            output_file = s3_uploader.uploader_data_dir() / NEXT_X_FILE
            output_file.write_text(
                json.dumps(self._next_point_workflows, indent=2, allow_nan=True) + "\n"
            )
            s3_uploader.upload_file(NEXT_X_FILE)

    def handle_surrogate_values(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        logger.info(
            "time_utc=%s source=%s capability=%s endpoint=%s",
            now,
            source,
            capability_name,
            endpoint_name,
        )

        normalized_payload = self._normalize_surrogate_values(payload)
        if normalized_payload is None:
            return

        if self._live_sink is not None:
            self._live_sink.handle_surrogate(normalized_payload)
        else:
            output_file = s3_uploader.uploader_data_dir() / SURROGATE_FILE
            output_file.write_text(json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n")
            s3_uploader.upload_file(SURROGATE_FILE)


class StorageEndpointHandlers:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        live_state: LiveStateStore | None = None,
        upload_outbox: UploadOutbox | None = None,
        websocket_manager: WebSocketManager | None = None,
    ) -> None:
        live_sink = None
        if live_state is not None and upload_outbox is not None and websocket_manager is not None:
            live_sink = LiveUpdateSink(
                live_state=live_state,
                upload_outbox=upload_outbox,
                websocket_manager=websocket_manager,
                data_dir=data_dir or s3_uploader.uploader_data_dir(),
            )
        self.accumulator = MeasurementAccumulator(data_dir=data_dir, live_sink=live_sink)
        self.dial_result_storage = DialResultStorage(data_dir=data_dir, live_sink=live_sink)

    def new_measurement(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        self.accumulator.handle_new_measurement(
            source=source,
            capability_name=capability_name,
            endpoint_name=endpoint_name,
            payload=payload,
        )

    def next_point(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        self.dial_result_storage.handle_next_point(
            source=source,
            capability_name=capability_name,
            endpoint_name=endpoint_name,
            payload=payload,
        )

    def surrogate_values(
        self,
        *,
        source: str,
        capability_name: str,
        endpoint_name: str,
        payload: INTERSECT_RESPONSE_VALUE,
    ) -> None:
        self.dial_result_storage.handle_surrogate_values(
            source=source,
            capability_name=capability_name,
            endpoint_name=endpoint_name,
            payload=payload,
        )


_legacy_handlers = StorageEndpointHandlers()
_accumulator = _legacy_handlers.accumulator
_dial_result_storage = _legacy_handlers.dial_result_storage


def new_measurement(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
    _legacy_handlers.new_measurement(
        source=source,
        capability_name=capability_name,
        endpoint_name=endpoint_name,
        payload=payload,
    )


def next_point(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
    _legacy_handlers.next_point(
        source=source,
        capability_name=capability_name,
        endpoint_name=endpoint_name,
        payload=payload,
    )


def surrogate_values(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
    _legacy_handlers.surrogate_values(
        source=source,
        capability_name=capability_name,
        endpoint_name=endpoint_name,
        payload=payload,
    )
