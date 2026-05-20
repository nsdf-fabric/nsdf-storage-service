from nsdf_storage_service.service import NsdfStorageCapability


def test_capability_has_expected_name():
    capability = NsdfStorageCapability()

    assert capability.intersect_sdk_capability_name == "nsdf_storage"


def test_status_reflects_listener_connection():
    capability = NsdfStorageCapability()

    assert capability.status() == "Idle"
    capability.set_listener_connected(True)
    assert capability.status() == "Listening"


def test_describe_returns_service_description():
    capability = NsdfStorageCapability()

    assert "new_measurement" in capability.describe()
