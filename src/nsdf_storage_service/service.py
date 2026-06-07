from intersect_sdk import IntersectBaseCapabilityImplementation, intersect_message, intersect_status
from .data_models import NewMeasurementData, NextPointData, SurrogateValuesData
from . import endpoints


def _dump_without_unset_dataset_size(payload):
    dumped = payload.model_dump()
    if "dataset_x_size" not in payload.model_fields_set:
        dumped.pop("dataset_x_size", None)
    return dumped


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
        return "NSDF storage service receives new_measurement, next_point, and surrogate_values messages"

    @intersect_message()
    def new_measurement(self, measurement: NewMeasurementData) -> None:
        """Receive a new CHESS measurement payload"""
        endpoints.new_measurement(
            source="direct-message",
            capability_name=self.intersect_sdk_capability_name,
            endpoint_name="new_measurement",
            payload=_dump_without_unset_dataset_size(measurement),
        )

    @intersect_message()
    def next_point(self, next_point: NextPointData) -> None:
        """Receive a DIAL next-point payload"""
        endpoints.next_point(
            source="direct-message",
            capability_name=self.intersect_sdk_capability_name,
            endpoint_name="next_point",
            payload=_dump_without_unset_dataset_size(next_point),
        )

    @intersect_message()
    def surrogate_values(self, surrogate_values: SurrogateValuesData) -> None:
        """Receive DIAL surrogate and uncertainty payload"""
        endpoints.surrogate_values(
            source="direct-message",
            capability_name=self.intersect_sdk_capability_name,
            endpoint_name="surrogate_values",
            payload=surrogate_values.model_dump(exclude_none=True),
        )
