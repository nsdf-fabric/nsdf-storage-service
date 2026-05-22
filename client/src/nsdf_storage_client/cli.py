from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from intersect_sdk import (
    ControlPlaneConfig,
    DataStoreConfigMap,
    IntersectClient,
    IntersectClientCallback,
    IntersectClientConfig,
    IntersectDirectMessageParams,
    default_intersect_lifecycle_loop,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _hierarchy_to_dot(hierarchy: dict[str, str]) -> str:
    keys = ("organization", "facility", "system", "subsystem", "service")
    return ".".join(str(hierarchy[k]) for k in keys)


def _build_response_callback():
    def callback(source: str, operation_id: str, has_error: bool, response) -> None:
        if has_error:
            logger.error("Error from %s (%s): %s", source, operation_id, response)
        else:
            logger.info("Response from %s (%s): %s", source, operation_id, response)

    return callback


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test measurement to nsdf-storage-service")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("local-conf.json"),
        help="Path to the INTERSECT config JSON file",
    )
    parser.add_argument("--labx", type=float, default=1.0, help="labx value")
    parser.add_argument("--labz", type=float, default=2.0, help="labz value")
    parser.add_argument("--center-value", type=float, default=3.0, help="center_value value")
    args = parser.parse_args()

    try:
        raw_config = _load_config(args.config)
    except (ValueError, OSError) as e:
        logger.critical("Unable to load config file: %s", e)
        return

    try:
        broker_cfg = raw_config["intersect"]["brokers"][0]
        hierarchy = raw_config["intersect-hierarchy"]
    except (KeyError, IndexError) as e:
        logger.critical("Invalid config: missing broker or hierarchy: %s", e)
        return

    destination = _hierarchy_to_dot(hierarchy)

    control_config = ControlPlaneConfig(
        protocol=broker_cfg["protocol"],
        username=broker_cfg["username"],
        password=broker_cfg["password"],
        host=broker_cfg["host"],
        port=broker_cfg["port"],
    )

    client_config = IntersectClientConfig(
        brokers=[control_config],
        data_stores=DataStoreConfigMap(),
        organization=hierarchy["organization"],
        facility=hierarchy["facility"],
        system="client-system",
        initial_message_event_config=IntersectClientCallback(
            messages_to_send=[
                IntersectDirectMessageParams(
                    destination=destination,
                    operation="nsdf_storage.new_measurement",
                    payload={
                        "labx": args.labx,
                        "labz": args.labz,
                        "center_value": args.center_value,
                    },
                )
            ]
        ),
        terminate_after_initial_messages=True,
    )

    client = IntersectClient(config=client_config, user_callback=_build_response_callback())
    default_intersect_lifecycle_loop(client)


if __name__ == "__main__":
    main()
