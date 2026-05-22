from intersect_sdk import IntersectBaseCapabilityImplementation, intersect_message, intersect_status
from .data_models import NewMeasurementData
from . import endpoints


class NsdfStorageCapability(IntersectBaseCapabilityImplementation):
    """INTERSECT capability for the NSDF storage service"""
    intersect_sdk_capability_name = "nsdf_storage"

    def __init__(self) -> None:
        super().__init__()

    @intersect_status()
    def status(self) -> str:
        return "Up"

    @intersect_message()
    def describe(self) -> str:
        return "NSDF storage service receives new_measurement messages"

    @intersect_message()
    def new_measurement(self, measurement: NewMeasurementData) -> None:
        """Receive a new CHESS measurement payload"""
        endpoints.new_measurement(
            source="direct-message",
            capability_name=self.intersect_sdk_capability_name,
            endpoint_name="new_measurement",
            payload=measurement.model_dump(),
        )

    
