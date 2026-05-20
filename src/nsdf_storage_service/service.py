from intersect_sdk import IntersectBaseCapabilityImplementation, intersect_message, intersect_status

from .data_models import NewMeasurementData
from .listener import handle_new_measurement


class NsdfStorageCapability(IntersectBaseCapabilityImplementation):
    """INTERSECT capability for the NSDF storage service."""

    intersect_sdk_capability_name = "nsdf_storage"

    def __init__(self) -> None:
        super().__init__()

    @intersect_message()
    def describe(self) -> str:
        """Describe the current storage service behavior."""
        return "NSDF storage service receives new_measurement messages"

    @intersect_message()
    def new_measurement(self, measurement: NewMeasurementData) -> None:
        """Receive a new CHESS measurement payload."""
        handle_new_measurement(
            source="direct-message",
            capability_name=self.intersect_sdk_capability_name,
            endpoint_name="new_measurement",
            payload=measurement.model_dump(),
        )

    @intersect_status()
    def status(self) -> str:
        """Return the storage service status."""
        return "Up"
