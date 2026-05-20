from __future__ import annotations

from intersect_sdk import IntersectBaseCapabilityImplementation, intersect_message, intersect_status


class NsdfStorageCapability(IntersectBaseCapabilityImplementation):
    """INTERSECT capability for the NSDF storage service."""

    intersect_sdk_capability_name = "nsdf_storage"

    def __init__(self) -> None:
        super().__init__()
        self._listener_connected = False

    def set_listener_connected(self, connected: bool) -> None:
        """Record whether the internal event listener is connected."""
        self._listener_connected = connected

    @intersect_message()
    def describe(self) -> str:
        """Describe the current storage service behavior."""
        return "NSDF storage service listening for new_measurement events"

    @intersect_status()
    def status(self) -> str:
        """Return the storage service listener status."""
        if self._listener_connected:
            return "Listening"
        return "Idle"
