from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_JSON_ENV_VAR = "NSDF_STORAGE_SERVICE_CONFIG_JSON"
CONFIG_FILE_ENV_VAR = "NSDF_STORAGE_SERVICE_CONFIG_FILE"
DEFAULT_CONFIG_FILE = "local-conf.json"


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON config file."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_runtime_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load service config from env JSON first, then config file fallback."""
    raw_env_config = os.environ.get(CONFIG_JSON_ENV_VAR)
    if raw_env_config:
        try:
            loaded = json.loads(raw_env_config)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {CONFIG_JSON_ENV_VAR}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{CONFIG_JSON_ENV_VAR} must contain a JSON object")
        return loaded

    config_path = path or os.environ.get(CONFIG_FILE_ENV_VAR, DEFAULT_CONFIG_FILE)
    return load_config(config_path)


def hierarchy_dict_to_dot(hierarchy: dict[str, str]) -> str:
    """Convert INTERSECT hierarchy config into dot notation."""
    required = ("organization", "facility", "system", "subsystem", "service")
    missing = [key for key in required if key not in hierarchy]
    if missing:
        raise ValueError(f"Missing hierarchy keys in config: {missing}")

    return ".".join(str(hierarchy[key]) for key in required)
