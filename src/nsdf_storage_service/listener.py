from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from intersect_sdk import INTERSECT_RESPONSE_VALUE

from .data_models import NewMeasurementData

logger = logging.getLogger(__name__)


def _normalize_payload(payload: INTERSECT_RESPONSE_VALUE) -> Any:
    if isinstance(payload, dict):
        try:
            return NewMeasurementData.model_validate(payload).model_dump()
        except ValueError:
            logger.warning("Received new_measurement payload that does not match expected model")
    return payload


def handle_new_measurement(
    *,
    source: str,
    capability_name: str,
    endpoint_name: str,
    payload: INTERSECT_RESPONSE_VALUE,
) -> None:
    """Handle one measurement message.

    This intentionally only prints the payload for now. Replace this function when the
    storage service begins moving payloads to an S3 bucket.
    """
    now = datetime.now(timezone.utc).isoformat()
    normalized_payload = _normalize_payload(payload)

    print("\n" + "=" * 100)
    print(f"time_utc:    {now}")
    print(f"source:      {source}")
    print(f"capability:  {capability_name}")
    print(f"endpoint:    {endpoint_name}")
    print("payload:")

    if isinstance(normalized_payload, (dict, list)):
        print(json.dumps(normalized_payload, indent=2, allow_nan=True))
    else:
        print(normalized_payload)

    print("=" * 100, flush=True)
