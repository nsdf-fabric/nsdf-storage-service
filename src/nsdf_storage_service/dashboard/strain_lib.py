from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

DEFAULT_GRID_SIZE = (26, 26)


@dataclass
class StrainFieldPlotConfig:
    grid_size: tuple[int, int] = field(default_factory=lambda: DEFAULT_GRID_SIZE)
    x_axis_label: str = "labx"
    y_axis_label: str = "labz"


@dataclass
class StrainFieldGrids:
    measurements: np.ndarray
    estimate: np.ndarray
    variance: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)


def validate_nsdf_measurement_doc(doc: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, Any]:
    if not isinstance(doc, Mapping):
        raise ValueError("NSDF data.json must be a JSON object.")
    dataset_x = doc.get("dataset_x")
    dataset_y = doc.get("dataset_y")
    if not isinstance(dataset_x, list) or not dataset_x:
        raise ValueError("'dataset_x' must be a non-empty list of coordinate pairs.")
    if not isinstance(dataset_y, list) or not dataset_y:
        raise ValueError("'dataset_y' must be a non-empty numeric 1D list.")
    if len(dataset_x) != len(dataset_y):
        raise ValueError("'dataset_x' length must match 'dataset_y' length.")

    coords = []
    for i, row in enumerate(dataset_x):
        if not isinstance(row, list) or len(row) < 2:
            raise ValueError(f"'dataset_x[{i}]' must contain labx/labz values.")
        coords.append((float(row[0]), float(row[1])))
    values = np.asarray(dataset_y, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("'dataset_y' must contain finite numeric values.")
    return np.asarray(coords, dtype=np.float64), values, _validate_bounds(doc.get("bounds"))


def normalize_measured_points(measurement: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if measurement is None:
        return []
    coords, values, _bounds = validate_nsdf_measurement_doc(measurement)
    return [
        {"labx": float(row[0]), "labz": float(row[1]), "center_value": float(value)}
        for row, value in zip(coords, values)
    ]


def normalize_surrogate_doc(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("Surrogate payload data must include surrogate and uncertainty arrays.")
    out: dict[str, Any] = {
        "workflow_id": payload.get("workflow_id"),
        "surrogate": data[0],
        "uncertainty": data[1],
    }
    if len(data) > 2:
        out["raw_uncertainty"] = data[2]
    return out


def normalize_next_points(next_x: list[dict[str, Any]]) -> dict[str, Any]:
    points = []
    for workflow in next_x:
        workflow_id = str(workflow.get("workflow_id", ""))
        data = workflow.get("data", [])
        if not isinstance(data, list):
            continue
        for index, coords in enumerate(data, start=1):
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            points.append(
                {
                    "workflow_id": workflow_id,
                    "labx": float(coords[0]),
                    "labz": float(coords[1]),
                    "sequence": index,
                }
            )
    return {"all": points, "latest": points[-1] if points else None}


def infer_nsdf_grid_size(data_doc: Mapping[str, Any]) -> tuple[int, int]:
    coords, _values, _bounds = validate_nsdf_measurement_doc(data_doc)
    nx = int(np.unique(coords[:, 0]).shape[0])
    ny = int(np.unique(coords[:, 1]).shape[0])
    return (nx, ny) if nx > 0 and ny > 0 else DEFAULT_GRID_SIZE


def build_strain_field_grids(
    doc: Mapping[str, Any],
    cfg: StrainFieldPlotConfig | None = None,
    surrogate_doc: Mapping[str, Any] | None = None,
) -> StrainFieldGrids:
    cfg = cfg or StrainFieldPlotConfig()
    nx, ny = cfg.grid_size
    coords, values, bounds = validate_nsdf_measurement_doc(doc)
    gx, gy = _norm_coordinates_to_grid(coords, nx, ny, bounds)

    mask = np.zeros((ny, nx), dtype=np.float64)
    for x, y in zip(gx, gy):
        ix = int(np.clip(round(float(x)), 0, nx - 1))
        iy = int(np.clip(round(float(y)), 0, ny - 1))
        mask[iy, ix] = 1.0

    surrogate_values = _numeric_field(surrogate_doc, "surrogate", values.shape[0])
    uncertainty = _numeric_field(surrogate_doc, "uncertainty", values.shape[0])
    estimate = _idw_fill_grid(
        gx, gy, surrogate_values if surrogate_values is not None else values, nx, ny
    )
    if uncertainty is not None:
        variance = _idw_fill_grid(gx, gy, np.square(np.maximum(uncertainty, 0.0)), nx, ny)
        variance_source = "uncertainty_squared"
    else:
        variance = _distance_placeholder(mask, float(np.nanmean(np.abs(values)) or 1.0) * 0.25)
        variance_source = "distance_placeholder"
    return StrainFieldGrids(
        measurements=mask,
        estimate=estimate,
        variance=variance,
        meta={
            "n_points": int(values.shape[0]),
            "estimate_source": "surrogate" if surrogate_values is not None else "dataset_y_idw",
            "variance_source": variance_source,
        },
    )


def state_to_dashboard_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    measurement = state.get("measurement")
    surrogate = state.get("surrogate")
    payload: dict[str, Any] = {
        "measured_points": state.get("measured_points", []),
        "next_points": state.get("next_points", {"all": [], "latest": None}),
        "grids": None,
    }
    if (
        isinstance(measurement, Mapping)
        and measurement.get("dataset_x")
        and measurement.get("dataset_y")
    ):
        grid_size = infer_nsdf_grid_size(measurement)
        cfg = StrainFieldPlotConfig(grid_size=grid_size)
        grids = build_strain_field_grids(
            measurement,
            cfg,
            surrogate if isinstance(surrogate, Mapping) else None,
        )
        payload["grids"] = {
            "grid_size": list(grid_size),
            "measurements": grids.measurements.tolist(),
            "estimate": grids.estimate.tolist(),
            "variance": grids.variance.tolist(),
            "meta": grids.meta,
        }
    return payload


def _validate_bounds(value: Any):
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        x0, x1 = float(value[0][0]), float(value[0][1])
        z0, z1 = float(value[1][0]), float(value[1][1])
    except (TypeError, ValueError, IndexError):
        return None
    if x0 == x1 or z0 == z1:
        return None
    return ((min(x0, x1), max(x0, x1)), (min(z0, z1), max(z0, z1)))


def _norm_coordinates_to_grid(coords: np.ndarray, nx: int, ny: int, bounds: Any):
    return _norm_positions_to_grid(coords[:, 0], coords[:, 1], nx, ny, bounds)


def _norm_positions_to_grid(labx: np.ndarray, labz: np.ndarray, nx: int, ny: int, bounds: Any):
    def scale(axis: np.ndarray, n: int, axis_bounds: Any):
        if axis_bounds is None:
            lo, hi = float(np.nanmin(axis)), float(np.nanmax(axis))
        else:
            lo, hi = axis_bounds
        if not math.isfinite(lo) or not math.isfinite(hi) or lo == hi:
            return np.full_like(axis, (n - 1) / 2.0)
        return (axis - lo) / (hi - lo) * (n - 1)

    return scale(labx, nx, bounds[0] if bounds else None), scale(
        labz, ny, bounds[1] if bounds else None
    )


def _numeric_field(doc: Mapping[str, Any] | None, key: str, expected_len: int):
    if not isinstance(doc, Mapping):
        return None
    value = doc.get(key)
    if not isinstance(value, list) or len(value) != expected_len:
        return None
    arr = np.asarray(value, dtype=np.float64)
    return arr if np.all(np.isfinite(arr)) else None


def _idw_fill_grid(px: np.ndarray, py: np.ndarray, values: np.ndarray, nx: int, ny: int):
    out = np.zeros((ny, nx), dtype=np.float64)
    xs = np.arange(nx, dtype=np.float64)
    ys = np.arange(ny, dtype=np.float64)
    mask = np.isfinite(values) & np.isfinite(px) & np.isfinite(py)
    if not np.any(mask):
        return out
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            d2 = np.square(px - x) + np.square(py - y) + 1e-12
            weights = 1.0 / d2[mask]
            out[i, j] = float(np.sum(weights * values[mask]) / np.sum(weights))
    return out


def _distance_placeholder(mask: np.ndarray, scale: float):
    occupied = mask > 0.5
    out = np.zeros(mask.shape, dtype=np.float64)
    ys, xs = np.indices(mask.shape)
    points = np.argwhere(occupied)
    if points.size == 0:
        return np.ones(mask.shape, dtype=np.float64) * scale
    for y in range(mask.shape[0]):
        for x in range(mask.shape[1]):
            distances = np.square(points[:, 0] - ys[y, x]) + np.square(points[:, 1] - xs[y, x])
            out[y, x] = math.sqrt(float(np.min(distances)))
    max_value = float(np.nanmax(out)) or 1.0
    return out / max_value * scale
