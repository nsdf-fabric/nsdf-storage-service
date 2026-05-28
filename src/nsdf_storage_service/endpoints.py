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


class MeasurementAccumulator:
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
            data_file = s3_uploader.uploader_data_dir() / "data.json"
            data_file.write_text(json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n")

            s3_uploader.upload_file("data.json")
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

        output_file = s3_uploader.uploader_data_dir() / SURROGATE_FILE
        output_file.write_text(json.dumps(normalized_payload, indent=2, allow_nan=True) + "\n")
        s3_uploader.upload_file(SURROGATE_FILE)


_accumulator = MeasurementAccumulator()
_dial_result_storage = DialResultStorage()


def new_measurement(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
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
    _dial_result_storage.handle_surrogate_values(
        source=source,
        capability_name=capability_name,
        endpoint_name=endpoint_name,
        payload=payload,
    )
