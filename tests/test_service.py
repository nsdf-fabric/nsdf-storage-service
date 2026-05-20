from unittest.mock import patch

from nsdf_storage_service.data_models import NewMeasurementData
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


def test_new_measurement_delegates_to_handler():
    capability = NsdfStorageCapability()
    measurement = NewMeasurementData(labx=1.0, labz=2.0, center_value=3.0)

    with patch("nsdf_storage_service.service.handle_new_measurement") as mock_handler:
        capability.new_measurement(measurement)

    mock_handler.assert_called_once_with(
        source="direct-message",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )
