import json

from nsdf_storage_service.endpoints import StorageEndpointHandlers
from nsdf_storage_service.live_state import LiveStateStore
from nsdf_storage_service.service import NsdfStorageCapability
from nsdf_storage_service.upload_outbox import UploadOutbox
from nsdf_storage_service.websocket_manager import WebSocketManager
from nsdf_storage_service.data_models import NewMeasurementData, NextPointData, SurrogateValuesData


class FakeUploader:
    def upload_file(self, file_name):
        return True


def _capability(tmp_path):
    live_state = LiveStateStore()
    ws = WebSocketManager()
    outbox = UploadOutbox(
        data_dir=tmp_path, uploader=FakeUploader(), live_state=live_state, websocket_manager=ws
    )
    handlers = StorageEndpointHandlers(
        data_dir=tmp_path,
        live_state=live_state,
        upload_outbox=outbox,
        websocket_manager=ws,
    )
    return NsdfStorageCapability(handlers=handlers), live_state, outbox


def test_live_capability_new_measurement_writes_updates_and_enqueues(tmp_path):
    capability, live_state, outbox = _capability(tmp_path)
    measurement = NewMeasurementData(dataset_x=[[1.0, 2.0]], dataset_y=[3.0], dim_x=2)

    capability.new_measurement(measurement)

    assert json.loads((tmp_path / "data.json").read_text())["dataset_y"] == [3.0]
    assert live_state.snapshot()["measurement_revision"] == 1
    assert live_state.snapshot()["s3"]["data.json"]["status"] == "pending"
    assert outbox.jobs_snapshot()[0]["file_name"] == "data.json"


def test_live_capability_next_point_and_surrogate_write_update_and_enqueue(tmp_path):
    capability, live_state, outbox = _capability(tmp_path)

    capability.next_point(NextPointData(workflow_id="w1", data=[1.0, 2.0]))
    capability.surrogate_values(SurrogateValuesData(workflow_id="w1", data=[[3.0], [0.1], [0.01]]))

    assert json.loads((tmp_path / "next_x.json").read_text()) == [
        {"workflow_id": "w1", "data": [[1.0, 2.0]]}
    ]
    assert json.loads((tmp_path / "surrogate.json").read_text())["surrogate"] == [3.0]
    snapshot = live_state.snapshot()
    assert snapshot["next_x_revision"] == 1
    assert snapshot["surrogate_revision"] == 1
    assert {job["file_name"] for job in outbox.jobs_snapshot()} == {
        "next_x.json",
        "surrogate.json",
    }
