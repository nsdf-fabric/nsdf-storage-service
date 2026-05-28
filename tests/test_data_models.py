import pytest
from pydantic import ValidationError

from nsdf_storage_service.data_models import NewMeasurementData, NextPointData, SurrogateValuesData


def test_new_measurement_data_accepts_data_service_payload():
    measurement = NewMeasurementData(
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        backend="sklearn",
        kernel="rbf",
        bounds=[[10.0, 0.0], [0.0, 10.0]],
        dim_x=2,
    )

    dumped = measurement.model_dump()
    assert dumped["dataset_x"] == [[1.0, 2.0], [3.0, 4.0]]
    assert dumped["dataset_y"] == [69.1, 69.2]
    assert dumped["backend"] == "sklearn"
    assert dumped["kernel"] == "rbf"
    assert dumped["bounds"] == [[0.0, 10.0], [0.0, 10.0]]
    assert dumped["dim_x"] == 2
    assert dumped["y_is_good"] is True


def test_new_measurement_data_rejects_missing_value():
    with pytest.raises(ValidationError):
        NewMeasurementData(
            dataset_x=[[1.0, 2.0]],
            backend="sklearn",
            kernel="rbf",
            bounds=[[0.0, 10.0], [0.0, 10.0]],
            dim_x=2,
        )


def test_new_measurement_data_rejects_dataset_length_mismatch():
    with pytest.raises(ValidationError, match="dataset_y length"):
        NewMeasurementData(
            dataset_x=[[1.0, 2.0], [3.0, 4.0]],
            dataset_y=[69.1],
            backend="sklearn",
            kernel="rbf",
            bounds=[[0.0, 10.0], [0.0, 10.0]],
            dim_x=2,
        )


def test_new_measurement_data_rejects_inconsistent_dataset_x_rows():
    with pytest.raises(ValidationError, match="Unequal vector lengths"):
        NewMeasurementData(
            dataset_x=[[1.0, 2.0], [3.0]],
            dataset_y=[69.1, 69.2],
            backend="sklearn",
            kernel="rbf",
            bounds=[[0.0, 10.0], [0.0, 10.0]],
            dim_x=2,
        )


def test_new_measurement_data_rejects_dim_x_mismatch():
    with pytest.raises(ValidationError, match="dim_x"):
        NewMeasurementData(
            dataset_x=[[1.0, 2.0]],
            dataset_y=[69.1],
            backend="sklearn",
            kernel="rbf",
            bounds=[[0.0, 10.0], [0.0, 10.0]],
            dim_x=1,
        )


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
