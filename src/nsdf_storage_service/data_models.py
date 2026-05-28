from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class NewMeasurementData(BaseModel):
    """Full workflow snapshot returned by DIAL get_workflow_data."""

    dataset_x: list[list[float]]
    dataset_y: list[float]
    backend: str
    kernel: Literal["rbf", "matern", "linear"]
    bounds: list[list[float]]
    y_is_good: bool = True
    seed: int = Field(default=-1, ge=-1, le=4294967295)
    dim_x: int = 1
    preprocess_log: bool = False
    preprocess_standardize: bool = False
    kernel_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None
    backend_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None
    extra_args: dict[str, float | int | bool | str | list[float] | tuple] | None = None

    @field_validator("dataset_x")
    @classmethod
    def _check_dataset_x_row_lengths(cls, dataset_x: list[list[float]]) -> list[list[float]]:
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
        if len(self.dataset_x) != len(self.dataset_y):
            raise ValueError("dataset_y length must equal dataset_x length")

        if self.dataset_x:
            expected_dim = len(self.dataset_x[0])
            if self.dim_x != expected_dim:
                raise ValueError("dim_x must equal the length of each dataset_x row")

        return self


class NextPointData(BaseModel):
    """Next point response returned by DIAL get_next_point."""

    workflow_id: str
    data: list[float] = Field(min_length=1)


class SurrogateValuesData(BaseModel):
    """Surrogate values response returned by DIAL get_surrogate_values."""

    workflow_id: str
    data: list[list[float]] = Field(min_length=2)

    @field_validator("data")
    @classmethod
    def _check_surrogate_payload(cls, data: list[list[float]]) -> list[list[float]]:
        if len(data) < 2:
            raise ValueError("data must include surrogate and uncertainty arrays")
        return data
