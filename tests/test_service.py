from unittest.mock import patch

from nsdf_storage_service.data_models import NewMeasurementData, NextPointData, SurrogateValuesData
from nsdf_storage_service.service import NsdfStorageCapability


def test_capability_has_expected_name():
    capability = NsdfStorageCapability()

    assert capability.intersect_sdk_capability_name == "nsdf_storage"


def test_status_reports_service_health():
    capability = NsdfStorageCapability()

    assert capability.status() == "Up"


def test_describe_returns_service_description():
    capability = NsdfStorageCapability()

    assert "new_measurement" in capability.describe()
    assert "next_point" in capability.describe()
    assert "surrogate_values" in capability.describe()


def test_new_measurement_delegates_to_handler():
    capability = NsdfStorageCapability()
    measurement = NewMeasurementData(
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        backend="sklearn",
        kernel="rbf",
        bounds=[[0.0, 10.0], [0.0, 10.0]],
        dim_x=2,
    )

    with patch("nsdf_storage_service.endpoints.new_measurement") as mock_handler:
        capability.new_measurement(measurement)

    expected_payload = measurement.model_dump()
    expected_payload.pop("workflow_id")
    expected_payload.pop("dataset_x_size")
    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload=expected_payload,
    )


def test_new_measurement_delegates_explicit_dataset_x_size_to_handler():
    capability = NsdfStorageCapability()
    measurement = NewMeasurementData(
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        dataset_x_size=2,
        backend="sklearn",
        kernel="rbf",
        bounds=[[0.0, 10.0], [0.0, 10.0]],
        dim_x=2,
    )

    with patch("nsdf_storage_service.endpoints.new_measurement") as mock_handler:
        capability.new_measurement(measurement)

    expected_payload = measurement.model_dump()
    expected_payload.pop("workflow_id")
    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload=expected_payload,
    )


def test_new_measurement_delegates_explicit_workflow_id_to_handler():
    capability = NsdfStorageCapability()
    measurement = NewMeasurementData(
        workflow_id="workflow-1",
        dataset_x=[[1.0, 2.0], [3.0, 4.0]],
        dataset_y=[69.1, 69.2],
        backend="sklearn",
        kernel="rbf",
        bounds=[[0.0, 10.0], [0.0, 10.0]],
        dim_x=2,
    )

    with patch("nsdf_storage_service.endpoints.new_measurement") as mock_handler:
        capability.new_measurement(measurement)

    expected_payload = measurement.model_dump()
    expected_payload.pop("dataset_x_size")
    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload=expected_payload,
    )


def test_new_measurement_annotation_is_resolved_for_intersect_sdk():
    annotation = NsdfStorageCapability.new_measurement.__annotations__["measurement"]

    assert annotation is NewMeasurementData


def test_next_point_delegates_to_handler():
    capability = NsdfStorageCapability()
    next_point = NextPointData(workflow_id="workflow-1", data=[1.0, 2.0])

    with patch("nsdf_storage_service.endpoints.next_point") as mock_handler:
        capability.next_point(next_point)

    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0]},
    )


def test_next_point_delegates_explicit_dataset_x_size_to_handler():
    capability = NsdfStorageCapability()
    next_point = NextPointData(
        workflow_id="workflow-1",
        data=[1.0, 2.0],
        dataset_x_size=3,
    )

    with patch("nsdf_storage_service.endpoints.next_point") as mock_handler:
        capability.next_point(next_point)

    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "dataset_x_size": 3, "data": [1.0, 2.0]},
    )


def test_surrogate_values_delegates_to_handler():
    capability = NsdfStorageCapability()
    surrogate_values = SurrogateValuesData(
        workflow_id="workflow-1",
        data=[[1.0, 2.0], [0.1, 0.2], [0.01, 0.02]],
    )

    with patch("nsdf_storage_service.endpoints.surrogate_values") as mock_handler:
        capability.surrogate_values(surrogate_values)

    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="surrogate_values",
        payload={
            "workflow_id": "workflow-1",
            "data": [[1.0, 2.0], [0.1, 0.2], [0.01, 0.02]],
        },
    )


def test_dial_result_annotations_are_resolved_for_intersect_sdk():
    next_point_annotation = NsdfStorageCapability.next_point.__annotations__["next_point"]
    surrogate_values_annotation = NsdfStorageCapability.surrogate_values.__annotations__[
        "surrogate_values"
    ]

    assert next_point_annotation is NextPointData
    assert surrogate_values_annotation is SurrogateValuesData
