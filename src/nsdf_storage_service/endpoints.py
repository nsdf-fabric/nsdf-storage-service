from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from intersect_sdk import INTERSECT_RESPONSE_VALUE

from . import s3_uploader
from .data_models import NewMeasurementData

logger = logging.getLogger(__name__)

class MeasurementAccumulator:
    def __init__(self) -> None:
        self._measurements: dict[str, list[float]] = {
            "labx": [],
            "labz": [],
            "center_value": [],
        }
        self._initialized: bool = False

    def _load_existing_state(self) -> None:
        """Restore accumulated measurements from file"""
        if self._initialized:
            return

        output_file = s3_uploader.uploader_data_dir() / "data.json"
        if output_file.exists():
            try:
                data = json.loads(output_file.read_text())
                if all(k in data for k in ("labx", "labz", "center_value")):
                    self._measurements["labx"] = data["labx"]
                    self._measurements["labz"] = data["labz"]
                    self._measurements["center_value"] = data["center_value"]
                    logger.info(
                        "Restored %d measurements from %s", len(data["labx"]), output_file
                    )
                else:
                    logger.warning("Existing data.json has unexpected structure; starting fresh")
            except (json.JSONDecodeError, ValueError):
                logger.warning("Existing data.json is corrupt; starting fresh")

        self._initialized = True

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
        """Accumulate a measurement into data.json and upload to S3"""
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
            self._load_existing_state()
            self._measurements["labx"].append(normalized_payload["labx"])
            self._measurements["labz"].append(normalized_payload["labz"])
            self._measurements["center_value"].append(normalized_payload["center_value"])

            data_file = s3_uploader.uploader_data_dir() / "data.json"
            data_file.write_text(
                json.dumps(self._measurements, indent=2, allow_nan=True) + "\n"
            )

            s3_uploader.upload_file("data.json")
        else:
            logger.warning(
                "Unexpected payload type: %s", type(normalized_payload).__name__
            )


_accumulator = MeasurementAccumulator()

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
