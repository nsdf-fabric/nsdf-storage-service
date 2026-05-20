import pytest
from pydantic import ValidationError

from nsdf_storage_service.data_models import NewMeasurementData


def test_new_measurement_data_accepts_data_service_payload():
    measurement = NewMeasurementData(labx=1.0, labz=2.0, center_value=3.0)

    assert measurement.model_dump() == {
        "labx": 1.0,
        "labz": 2.0,
        "center_value": 3.0,
    }


def test_new_measurement_data_rejects_missing_value():
    with pytest.raises(ValidationError):
        NewMeasurementData(labx=1.0, labz=2.0)
