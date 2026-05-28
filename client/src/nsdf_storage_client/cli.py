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
    parser = argparse.ArgumentParser(
        description="Send a test workflow snapshot to nsdf-storage-service"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("local-conf.json"),
        help="Path to the INTERSECT config JSON file",
    )
    parser.add_argument(
        "--dataset-x",
        default="[[1.0, 2.0], [3.0, 4.0]]",
        help="JSON list of input vectors. Default: [[1.0, 2.0], [3.0, 4.0]]",
    )
    parser.add_argument(
        "--dataset-y",
        default="[69.1, 69.2]",
        help="JSON list of output values. Default: [69.1, 69.2]",
    )
    parser.add_argument("--backend", default="sklearn", help="DIAL backend name")
    parser.add_argument(
        "--kernel",
        default="rbf",
        choices=("rbf", "matern", "linear"),
        help="DIAL kernel name",
    )
    parser.add_argument(
        "--bounds",
        default="[[0.0, 10.0], [0.0, 10.0]]",
        help="JSON list of bounds. Default: [[0.0, 10.0], [0.0, 10.0]]",
    )
    parser.add_argument("--dim-x", type=int, default=2, help="Input dimension")
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
    try:
        dataset_x = json.loads(args.dataset_x)
        dataset_y = json.loads(args.dataset_y)
        bounds = json.loads(args.bounds)
    except json.JSONDecodeError as e:
        logger.critical("Unable to parse workflow JSON arguments: %s", e)
        return

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
                        "dataset_x": dataset_x,
                        "dataset_y": dataset_y,
                        "backend": args.backend,
                        "kernel": args.kernel,
                        "bounds": bounds,
                        "dim_x": args.dim_x,
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
