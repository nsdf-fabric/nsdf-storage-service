from pydantic import BaseModel, Field, field_validator


class NewMeasurementData(BaseModel):
    """A single measurement emitted by intersect-chess-data-service."""

    labx: float
    labz: float
    center_value: float


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
