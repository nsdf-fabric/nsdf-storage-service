import pytest
from pydantic import ValidationError

from nsdf_storage_service.data_models import NewMeasurementData, NextPointData, SurrogateValuesData


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


def test_next_point_data_accepts_dial_response_payload():
    next_point = NextPointData(workflow_id="workflow-1", data=[1.0, 2.0])

    assert next_point.model_dump() == {
        "workflow_id": "workflow-1",
        "data": [1.0, 2.0],
    }


def test_surrogate_values_data_accepts_surrogate_and_uncertainty_payload():
    surrogate = SurrogateValuesData(
        workflow_id="workflow-1",
        data=[
            [1.0, 2.0],
            [0.1, 0.2],
            [0.01, 0.02],
        ],
    )

    assert surrogate.model_dump() == {
        "workflow_id": "workflow-1",
        "data": [
            [1.0, 2.0],
            [0.1, 0.2],
            [0.01, 0.02],
        ],
    }


def test_surrogate_values_data_rejects_missing_uncertainty():
    with pytest.raises(ValidationError):
        SurrogateValuesData(workflow_id="workflow-1", data=[[1.0, 2.0]])
