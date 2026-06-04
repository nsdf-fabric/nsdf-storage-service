#!/usr/bin/env python3
"""Send live-changing payloads to all nsdf-storage-service endpoints.

Run the integrated service first, open the dashboard, then run this script.
Each cycle sends:

1. nsdf_storage.new_measurement
2. nsdf_storage.next_point
3. nsdf_storage.surrogate_values

The measurement snapshot grows every cycle, so the dashboard should visibly update.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from intersect_sdk import (
    ControlPlaneConfig,
    DataStoreConfigMap,
    IntersectClient,
    IntersectClientCallback,
    IntersectClientConfig,
    IntersectDirectMessageParams,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def hierarchy_to_dot(hierarchy: dict[str, str]) -> str:
    keys = ("organization", "facility", "system", "subsystem", "service")
    missing = [key for key in keys if key not in hierarchy]
    if missing:
        raise ValueError(f"Missing hierarchy keys: {missing}")
    return ".".join(str(hierarchy[key]) for key in keys)


def build_cycle_messages(
    *,
    destination: str,
    workflow_id: str,
    cycle: int,
    measured_points: list[list[float]],
    measured_values: list[float],
    next_point: list[float],
) -> list[IntersectDirectMessageParams]:
    surrogate = [round(value + 0.15, 3) for value in measured_values]
    uncertainty = [round(0.08 + (idx % 4) * 0.03, 3) for idx in range(len(measured_values))]
    raw_uncertainty = [round(value / 2.0, 3) for value in uncertainty]

    return [
        IntersectDirectMessageParams(
            destination=destination,
            operation="nsdf_storage.new_measurement",
            payload={
                "dataset_x": measured_points,
                "dataset_y": measured_values,
                "backend": "sklearn",
                "kernel": "rbf",
                "bounds": [[0.0, 26.0], [0.0, 26.0]],
                "dim_x": 2,
            },
        ),
        IntersectDirectMessageParams(
            destination=destination,
            operation="nsdf_storage.next_point",
            payload={
                "workflow_id": workflow_id,
                "data": next_point,
            },
        ),
        IntersectDirectMessageParams(
            destination=destination,
            operation="nsdf_storage.surrogate_values",
            payload={
                "workflow_id": workflow_id,
                "data": [surrogate, uncertainty, raw_uncertainty],
            },
        ),
    ]


def build_client_config(
    raw_config: dict[str, Any],
    *,
    client_system: str,
    workflow_id: str,
    cycle: int,
    measured_points: list[list[float]],
    measured_values: list[float],
    next_point: list[float],
) -> IntersectClientConfig:
    broker_cfg = raw_config["intersect"]["brokers"][0]
    hierarchy = raw_config["intersect-hierarchy"]
    destination = hierarchy_to_dot(hierarchy)
    control_config = ControlPlaneConfig(
        protocol=broker_cfg["protocol"],
        username=broker_cfg["username"],
        password=broker_cfg["password"],
        host=broker_cfg["host"],
        port=broker_cfg["port"],
    )
    return IntersectClientConfig(
        brokers=[control_config],
        data_stores=DataStoreConfigMap(),
        organization=hierarchy["organization"],
        facility=hierarchy["facility"],
        system=f"{client_system}-{cycle}",
        initial_message_event_config=IntersectClientCallback(
            messages_to_send=build_cycle_messages(
                destination=destination,
                workflow_id=workflow_id,
                cycle=cycle,
                measured_points=measured_points,
                measured_values=measured_values,
                next_point=next_point,
            )
        ),
        terminate_after_initial_messages=False,
    )


def build_response_callback():
    def callback(source: str, operation_id: str, has_error: bool, response: Any) -> None:
        if has_error:
            logger.error("Error from %s (%s): %s", source, operation_id, response)
        else:
            logger.info("Response from %s (%s): %s", source, operation_id, response)

    return callback


def main() -> None:
    parser = argparse.ArgumentParser(description="Send live dashboard demo updates.")
    parser.add_argument("--config", type=Path, default=Path("local-conf.json"))
    parser.add_argument("--workflow-id", default="dashboard-demo")
    parser.add_argument("--client-system", default="nsdf-storage-live-demo-client")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--hold", type=float, default=1.0)
    args = parser.parse_args()

    raw_config = load_config(args.config)
    measured_points = [[2.0, 2.0], [6.0, 4.0], [10.0, 8.0]]
    measured_values = [measurement_value(point, 0) for point in measured_points]
    next_point = propose_next_point(measured_points, 1)

    for cycle in range(1, args.cycles + 1):
        if cycle > 1:
            measured_points.append(next_point)
            measured_values.append(measurement_value(next_point, cycle))
            next_point = propose_next_point(measured_points, cycle)

        logger.info("Sending live dashboard update cycle %s/%s", cycle, args.cycles)
        logger.info("Measured points: %s", measured_points)
        logger.info("Suggested next point: %s", next_point)
        client = IntersectClient(
            config=build_client_config(
                raw_config,
                client_system=args.client_system,
                workflow_id=args.workflow_id,
                cycle=cycle,
                measured_points=measured_points,
                measured_values=measured_values,
                next_point=next_point,
            ),
            user_callback=build_response_callback(),
        )
        client.startup()
        try:
            time.sleep(args.hold)
        finally:
            client.shutdown(f"Completed live dashboard update cycle {cycle}")
        if cycle < args.cycles:
            time.sleep(args.interval)


def measurement_value(point: list[float], cycle: int) -> float:
    labx, labz = point
    return round(68.0 + labx * 0.18 + labz * 0.11 + cycle * 0.35, 3)


def propose_next_point(measured_points: list[list[float]], cycle: int) -> list[float]:
    candidates = [
        [14.0, 10.0],
        [18.0, 14.0],
        [22.0, 18.0],
        [24.0, 22.0],
        [20.0, 24.0],
        [16.0, 20.0],
        [12.0, 16.0],
        [8.0, 12.0],
    ]
    measured = {tuple(point) for point in measured_points}
    for offset in range(len(candidates)):
        candidate = candidates[(cycle + offset - 1) % len(candidates)]
        if tuple(candidate) not in measured:
            return candidate
    return [float((cycle * 3) % 26), float((cycle * 5) % 26)]


if __name__ == "__main__":
    main()
