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
    assert dumped["workflow_id"] is None
    assert dumped["dataset_x"] == [[1.0, 2.0], [3.0, 4.0]]
    assert dumped["dataset_y"] == [69.1, 69.2]
    assert dumped["dataset_x_size"] is None
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
        "dataset_x_size": None,
        "data": [1.0, 2.0],
    }


def test_next_point_data_accepts_dataset_x_size():
    next_point = NextPointData(workflow_id="workflow-1", data=[1.0, 2.0], dataset_x_size=3)

    assert next_point.dataset_x_size == 3


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
        "dataset_x_size": None,
        "data": [
            [1.0, 2.0],
            [0.1, 0.2],
            [0.01, 0.02],
        ],
        "values": None,
        "transformed_stddevs": None,
        "transformed_stddevs_avg": None,
        "stddevs": None,
        "dim_x": None,
        "bounds": None,
        "points_to_predict": None,
    }


def test_surrogate_values_data_accepts_expanded_dial_payload():
    surrogate = SurrogateValuesData(
        workflow_id="workflow-1",
        dataset_x_size=2,
        values=[1.0, 2.0],
        transformed_stddevs=[0.1, 0.2],
        transformed_stddevs_avg=0.15,
        stddevs=[0.01, 0.02],
        dim_x=2,
        bounds=[[24.0, 0.0], [0.0, 24.0]],
        points_to_predict=[[1.0, 2.0], [3.0, 4.0]],
    )

    assert surrogate.surrogate_values == [1.0, 2.0]
    assert surrogate.uncertainty_values == [0.1, 0.2]
    assert surrogate.raw_uncertainty_values == [0.01, 0.02]
    assert surrogate.bounds == [[0.0, 24.0], [0.0, 24.0]]
    assert surrogate.dataset_x_size == 2
    assert surrogate.transformed_stddevs_avg == 0.15


def test_surrogate_values_data_rejects_missing_uncertainty():
    with pytest.raises(ValidationError):
        SurrogateValuesData(workflow_id="workflow-1", data=[[1.0, 2.0]])


def test_surrogate_values_data_rejects_incomplete_expanded_payload():
    with pytest.raises(ValidationError, match="Missing expanded surrogate fields"):
        SurrogateValuesData(
            workflow_id="workflow-1",
            values=[1.0, 2.0],
            transformed_stddevs=[0.1, 0.2],
        )


def test_surrogate_values_data_rejects_expanded_length_mismatch():
    with pytest.raises(ValidationError, match="lengths must match"):
        SurrogateValuesData(
            workflow_id="workflow-1",
            values=[1.0, 2.0],
            transformed_stddevs=[0.1],
            stddevs=[0.01, 0.02],
            dim_x=2,
            bounds=[[0.0, 24.0], [0.0, 24.0]],
            points_to_predict=[[1.0, 2.0], [3.0, 4.0]],
        )


def test_surrogate_values_data_rejects_points_that_do_not_match_dim_x():
    with pytest.raises(ValidationError, match="points_to_predict rows"):
        SurrogateValuesData(
            workflow_id="workflow-1",
            values=[1.0],
            transformed_stddevs=[0.1],
            stddevs=[0.01],
            dim_x=2,
            bounds=[[0.0, 24.0], [0.0, 24.0]],
            points_to_predict=[[1.0]],
        )


def test_new_measurement_data_accepts_dataset_x_size():
    measurement = NewMeasurementData(
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        dataset_x_size=2,
        dim_x=2,
    )

    assert measurement.dataset_x_size == 2


def test_new_measurement_data_accepts_workflow_id():
    measurement = NewMeasurementData(
        workflow_id="workflow-1",
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        dim_x=2,
    )

    assert measurement.workflow_id == "workflow-1"
