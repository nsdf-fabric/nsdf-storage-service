from pydantic import BaseModel


class NewMeasurementData(BaseModel):
    """A single measurement emitted by intersect-chess-data-service."""

    labx: float
    labz: float
    center_value: float
