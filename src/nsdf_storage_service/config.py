from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
