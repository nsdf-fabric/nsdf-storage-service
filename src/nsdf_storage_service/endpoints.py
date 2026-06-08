from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from intersect_sdk import INTERSECT_RESPONSE_VALUE

from . import s3_uploader
from .data_models import NewMeasurementData, NextPointData, SurrogateValuesData

logger = logging.getLogger(__name__)


NEXT_X_FILE = "next_x.json"
SURROGATE_FILE = "surrogate.json"


def _log_received_payload(endpoint_name: str, payload: INTERSECT_RESPONSE_VALUE) -> None:
    logger.info("Received %s payload: %s", endpoint_name, payload)


class MeasurementAccumulator:
    def _normalize_payload(self, payload: INTERSECT_RESPONSE_VALUE) -> Any:
        """Validate and dump payload as a dict, warn on mismatch."""
        if isinstance(payload, dict):
            try:
                normalized = NewMeasurementData.model_validate(payload).model_dump()
                if "dataset_x_size" not in payload:
                    normalized.pop("dataset_x_size", None)
                return normalized
            except ValueError:
                logger.warning(
                    "Received new_measurement payload that does not match expected model"
                )
        return payload

    def _load_existing_snapshot(self) -> dict[str, Any]:
        data_file = s3_uploader.uploader_data_dir() / "data.json"
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
            dataset_x_size = normalized_payload.get("dataset_x_size")
            data_file = s3_uploader.uploader_data_dir() / "data.json"
            data_file.write_text(json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n")

            s3_uploader.upload_file("data.json", dataset_x_size=dataset_x_size)
        else:
            logger.warning("Unexpected payload type: %s", type(normalized_payload).__name__)


class DialResultStorage:
    def __init__(self) -> None:
        self._next_point_workflows: list[dict[str, Any]] = []
        self._next_points_initialized = False

    def _load_existing_next_points(self) -> None:
        if self._next_points_initialized:
            return

        output_file = s3_uploader.uploader_data_dir() / NEXT_X_FILE
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
                    "dataset_x_size": next_point.dataset_x_size,
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
                    "surrogate": surrogate_values.surrogate_values,
                    "uncertainty": surrogate_values.uncertainty_values,
                }
                if surrogate_values.dataset_x_size is not None:
                    normalized["dataset_x_size"] = surrogate_values.dataset_x_size
                if surrogate_values.transformed_stddevs_avg is not None:
                    normalized["transformed_stddevs_avg"] = surrogate_values.transformed_stddevs_avg
                raw_uncertainty = surrogate_values.raw_uncertainty_values
                if raw_uncertainty is not None:
                    normalized["raw_uncertainty"] = raw_uncertainty
                if surrogate_values.dim_x is not None:
                    normalized["dim_x"] = surrogate_values.dim_x
                if surrogate_values.bounds is not None:
                    normalized["bounds"] = surrogate_values.bounds
                if surrogate_values.points_to_predict is not None:
                    normalized["points_to_predict"] = surrogate_values.points_to_predict
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
        dataset_x_size = normalized_payload.get("dataset_x_size")
        for workflow in self._next_point_workflows:
            if workflow.get("workflow_id") == workflow_id:
                workflow.setdefault("data", []).append(next_point)
                if dataset_x_size is not None:
                    workflow["dataset_x_size"] = dataset_x_size
                break
        else:
            workflow = {
                "workflow_id": workflow_id,
                "data": [next_point],
            }
            if dataset_x_size is not None:
                workflow["dataset_x_size"] = dataset_x_size
            self._next_point_workflows.append(workflow)

        output_file = s3_uploader.uploader_data_dir() / NEXT_X_FILE
        output_file.write_text(
            json.dumps(self._next_point_workflows, indent=2, allow_nan=True) + "\n"
        )
        s3_uploader.upload_file(NEXT_X_FILE, dataset_x_size=dataset_x_size)

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

        output_file = s3_uploader.uploader_data_dir() / SURROGATE_FILE
        output_file.write_text(json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n")
        s3_uploader.upload_file(
            SURROGATE_FILE,
            dataset_x_size=normalized_payload.get("dataset_x_size"),
        )


_accumulator = MeasurementAccumulator()
_dial_result_storage = DialResultStorage()


def new_measurement(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
    _log_received_payload(endpoint_name, payload)
    _accumulator.handle_new_measurement(
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
    _log_received_payload(endpoint_name, payload)
    _dial_result_storage.handle_next_point(
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
    _log_received_payload(endpoint_name, payload)
    _dial_result_storage.handle_surrogate_values(
        source=source,
        capability_name=capability_name,
        endpoint_name=endpoint_name,
        payload=payload,
    )
