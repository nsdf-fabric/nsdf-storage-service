from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from intersect_sdk import IntersectClient, IntersectService, IntersectServiceConfig
from intersect_sdk import default_intersect_lifecycle_loop

from .config import build_client_config, get_source_event_config, load_config
from .listener import event_callback
from .service import NsdfStorageCapability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="NSDF Storage INTERSECT Service")
    parser.add_argument(
        "--config",
        type=Path,
        default=os.environ.get("NSDF_STORAGE_SERVICE_CONFIG_FILE", "local-conf.json"),
    )
    args = parser.parse_args()

    try:
        raw_config = load_config(args.config)
    except (ValueError, OSError) as e:
        logger.critical("Unable to load config file: %s", e)
        sys.exit(1)

    try:
        service_config = IntersectServiceConfig(
            hierarchy=raw_config["intersect-hierarchy"],
            **raw_config["intersect"],
        )
        client_config = build_client_config(raw_config)
    except (KeyError, ValueError) as e:
        logger.critical("Invalid config file: %s", e)
        sys.exit(1)

    capability = NsdfStorageCapability()
    service = IntersectService([capability], service_config)
    client = IntersectClient(
        config=client_config,
        event_callback=event_callback,
    )

    source_event = get_source_event_config(raw_config)

    def start_listener() -> None:
        logger.info(
            "Listening for event hierarchy=%s capability=%s event=%s",
            source_event["hierarchy"],
            source_event["capability"],
            source_event["event"],
        )
        client.startup()
        capability.set_listener_connected(client.is_connected())

    def cleanup_listener(_signal_code: int) -> None:
        capability.set_listener_connected(False)
        client.shutdown("NSDF storage service shutting down")

    def refresh_listener_status(_service: IntersectService) -> None:
        capability.set_listener_connected(client.is_connected())

    default_intersect_lifecycle_loop(
        service,
        post_startup_callback=start_listener,
        cleanup_callback=cleanup_listener,
        waiting_callback=refresh_listener_status,
    )


if __name__ == "__main__":
    main()
