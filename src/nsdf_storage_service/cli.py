from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from intersect_sdk import IntersectService, IntersectServiceConfig
from intersect_sdk import default_intersect_lifecycle_loop

from .config import load_config
from .service import NsdfStorageCapability
from .s3_uploader import init_s3

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
    except (KeyError, ValueError) as e:
        logger.critical("Invalid config file: %s", e)
        sys.exit(1)

    # initialize s3 uploader
    init_s3(raw_config.get("s3", {}))

    capability = NsdfStorageCapability()
    service = IntersectService([capability], service_config)

    logger.info("Starting NSDF storage service")
    default_intersect_lifecycle_loop(service)


if __name__ == "__main__":
    main()
