from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from intersect_sdk import (
    IntersectClientCallback,
    IntersectClientConfig,
    IntersectEventMessageParams,
)

DEFAULT_SOURCE_CAPABILITY = "chess_data_egress"
DEFAULT_SOURCE_EVENT = "new_measurement"


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON config file."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def hierarchy_dict_to_dot(hierarchy: dict[str, str]) -> str:
    """Convert INTERSECT hierarchy config into dot notation."""
    required = ("organization", "facility", "system", "subsystem", "service")
    missing = [key for key in required if key not in hierarchy]
    if missing:
        raise ValueError(f"Missing hierarchy keys in config: {missing}")

    return ".".join(str(hierarchy[key]) for key in required)


def get_source_event_config(raw_config: dict[str, Any]) -> dict[str, str]:
    """Return source event configuration, applying data-service-compatible defaults."""
    source_event = raw_config.get("source-event", {})

    hierarchy = source_event.get("hierarchy")
    if hierarchy is None:
        hierarchy = hierarchy_dict_to_dot(
            {
                "organization": "chess",
                "facility": "chess-facility",
                "system": "data-egress-system",
                "subsystem": "data-egress-subsystem",
                "service": "chess-data-egress-service",
            }
        )
    elif isinstance(hierarchy, dict):
        hierarchy = hierarchy_dict_to_dot(hierarchy)

    return {
        "hierarchy": str(hierarchy),
        "capability": str(source_event.get("capability", DEFAULT_SOURCE_CAPABILITY)),
        "event": str(source_event.get("event", DEFAULT_SOURCE_EVENT)),
    }


def build_client_config(raw_config: dict[str, Any]) -> IntersectClientConfig:
    """Build an INTERSECT client config that subscribes to the source measurement event."""
    if "intersect" not in raw_config or "brokers" not in raw_config["intersect"]:
        raise ValueError("Expected config file to contain ['intersect']['brokers']")

    source_event = get_source_event_config(raw_config)
    event_to_listen_for = IntersectEventMessageParams(
        hierarchy=source_event["hierarchy"],
        capability_name=source_event["capability"],
        event_name=source_event["event"],
    )

    client_identity = raw_config.get("listener-client", {})
    return IntersectClientConfig(
        brokers=raw_config["intersect"]["brokers"],
        organization=client_identity.get("organization", "chess"),
        facility=client_identity.get("facility", "chess-facility"),
        system=client_identity.get("system", "nsdf-storage-listener-system"),
        terminate_after_initial_messages=False,
        initial_message_event_config=IntersectClientCallback(
            services_to_start_listening_for_events=[event_to_listen_for],
        ),
    )
