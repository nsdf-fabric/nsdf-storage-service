from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class NewMeasurementData(BaseModel):
    """Measurement payload accepted by nsdf storage.

    Supports either:
    - Full snapshot shape (dataset_x + dataset_y + metadata)
    - Point shape (next_x + next_y) used in campaign task wiring
    - Event point shape (labx + labz + center_value)
    """

    workflow_id: str | None = None
    dataset_x: list[list[float]] | None = None
    dataset_y: list[float] | None = None
    dataset_x_size: int | None = Field(default=None, ge=0)
    backend: str = "sklearn"
    kernel: Literal["rbf", "matern", "linear"] = "rbf"
    bounds: list[list[float]] = Field(default_factory=lambda: [[-47.33, 26.17], [-255.3, -242.3]])
    y_is_good: bool = True
    seed: int = Field(default=-1, ge=-1, le=4294967295)
    dim_x: int = 2
    preprocess_log: bool = False
    preprocess_standardize: bool = False
    kernel_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None
    backend_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None
    extra_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None

    next_x: list[float] | None = None
    next_y: float | None = None
    labx: float | None = None
    labz: float | None = None
    center_value: float | None = None

    @field_validator("dataset_x")
    @classmethod
    def _check_dataset_x_row_lengths(
        cls, dataset_x: list[list[float]] | None
    ) -> list[list[float]] | None:
        if dataset_x is None:
            return dataset_x
        if len(dataset_x) < 2:
            return dataset_x

        target_length = len(dataset_x[0])
        for row in dataset_x[1:]:
            if len(row) != target_length:
                raise ValueError("Unequal vector lengths in dataset_x")
        return dataset_x

    @field_validator("bounds")
    @classmethod
    def _check_and_sort_bounds(cls, bounds: list[list[float]]) -> list[list[float]]:
        for row in bounds:
            if len(row) != 2:
                raise ValueError("Each bounds row must contain exactly two values")
            row.sort()
        return bounds

    @model_validator(mode="after")
    def _check_dataset_lengths_and_dimension(self):
        has_snapshot = self.dataset_x is not None or self.dataset_y is not None
        has_next_point = self.next_x is not None or self.next_y is not None
        has_event_point = (
            self.labx is not None or self.labz is not None or self.center_value is not None
        )

        if not (has_snapshot or has_next_point or has_event_point):
            raise ValueError(
                "Must provide snapshot fields, next point fields, or event point fields"
            )

        if self.dataset_x is not None or self.dataset_y is not None:
            if self.dataset_x is None or self.dataset_y is None:
                raise ValueError("dataset_x and dataset_y must be provided together")
            if len(self.dataset_x) != len(self.dataset_y):
                raise ValueError("dataset_y length must equal dataset_x length")

        if self.dataset_x:
            expected_dim = len(self.dataset_x[0])
            if self.dim_x != expected_dim:
                raise ValueError("dim_x must equal the length of each dataset_x row")

        if self.next_x is not None or self.next_y is not None:
            if self.next_x is None or self.next_y is None:
                raise ValueError("next_x and next_y must be provided together")
            if len(self.next_x) < 2:
                raise ValueError("next_x must have at least 2 coordinates")

        if self.labx is not None or self.labz is not None or self.center_value is not None:
            if self.labx is None or self.labz is None or self.center_value is None:
                raise ValueError("labx, labz, and center_value must be provided together")

        return self


class NextPointData(BaseModel):
    """Next point response returned by DIAL get_next_point."""

    workflow_id: str
    dataset_x_size: int | None = Field(default=None, ge=0)
    data: list[float] = Field(min_length=1)


class SurrogateValuesData(BaseModel):
    """Surrogate values response returned by DIAL get_surrogate_values."""

    workflow_id: str
    dataset_x_size: int | None = Field(default=None, ge=0)
    data: list[list[float]] | None = None
    values: list[float] | None = None
    transformed_stddevs: list[float] | None = None
    transformed_stddevs_avg: float | None = None
    stddevs: list[float] | None = None
    dim_x: int | None = None
    bounds: list[list[float]] | None = None
    points_to_predict: list[list[float]] | None = None

    @field_validator("data")
    @classmethod
    def _check_surrogate_payload(cls, data: list[list[float]] | None) -> list[list[float]] | None:
        if data is None:
            return data
        if len(data) < 2:
            raise ValueError("data must include surrogate and uncertainty arrays")
        return data

    @field_validator("bounds")
    @classmethod
    def _check_surrogate_bounds(cls, bounds: list[list[float]] | None) -> list[list[float]] | None:
        if bounds is None:
            return bounds
        for row in bounds:
            if len(row) != 2:
                raise ValueError("Each bounds row must contain exactly two values")
            row.sort()
        return bounds

    @model_validator(mode="after")
    def _check_surrogate_shape(self):
        has_legacy_data = self.data is not None
        new_shape_fields = (
            self.values,
            self.transformed_stddevs,
            self.stddevs,
            self.dim_x,
            self.bounds,
            self.points_to_predict,
        )
        has_new_shape = any(field is not None for field in new_shape_fields)

        if not has_legacy_data and not has_new_shape:
            raise ValueError("Must provide legacy data or expanded surrogate fields")

        if has_new_shape:
            missing = [
                name
                for name, value in (
                    ("values", self.values),
                    ("transformed_stddevs", self.transformed_stddevs),
                    ("stddevs", self.stddevs),
                    ("dim_x", self.dim_x),
                    ("bounds", self.bounds),
                    ("points_to_predict", self.points_to_predict),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"Missing expanded surrogate fields: {missing}")

            if len(self.values) != len(self.transformed_stddevs) or len(self.values) != len(
                self.stddevs
            ):
                raise ValueError("values, transformed_stddevs, and stddevs lengths must match")

            for point in self.points_to_predict:
                if len(point) != self.dim_x:
                    raise ValueError("points_to_predict rows must match dim_x")

            if len(self.bounds) != self.dim_x:
                raise ValueError("bounds length must match dim_x")

        return self

    @property
    def surrogate_values(self) -> list[float]:
        if self.values is not None:
            return self.values
        return self.data[0]

    @property
    def uncertainty_values(self) -> list[float]:
        if self.transformed_stddevs is not None:
            return self.transformed_stddevs
        return self.data[1]

    @property
    def raw_uncertainty_values(self) -> list[float] | None:
        if self.stddevs is not None:
            return self.stddevs
        if self.data is not None and len(self.data) > 2:
            return self.data[2]
        return None
