import asyncio

from nsdf_storage_service.live_state import LiveStateStore
from nsdf_storage_service.upload_outbox import UploadOutbox


class FakeUploader:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.uploaded = []

    def upload_file(self, file_name):
        self.uploaded.append(file_name)
        if self.fail:
            raise RuntimeError("upload failed")
        return True


def test_upload_outbox_enqueue_marks_pending(tmp_path):
    state = LiveStateStore()
    outbox = UploadOutbox(data_dir=tmp_path, uploader=FakeUploader(), live_state=state)

    outbox.enqueue_sync("data.json")

    assert outbox.jobs_snapshot()[0]["file_name"] == "data.json"
    assert state.snapshot()["s3"]["data.json"]["status"] == "pending"


def test_upload_outbox_marks_persisted_on_success(tmp_path):
    state = LiveStateStore()
    uploader = FakeUploader()
    outbox = UploadOutbox(data_dir=tmp_path, uploader=uploader, live_state=state)
    outbox.enqueue_sync("data.json")

    asyncio.run(outbox.process_once())

    assert uploader.uploaded == ["data.json"]
    assert outbox.jobs_snapshot() == []
    assert state.snapshot()["s3"]["data.json"]["status"] == "persisted"


def test_upload_outbox_marks_failed_and_keeps_retryable_job(tmp_path):
    state = LiveStateStore()
    outbox = UploadOutbox(data_dir=tmp_path, uploader=FakeUploader(fail=True), live_state=state)
    outbox.enqueue_sync("data.json")

    asyncio.run(outbox.process_once())

    jobs = outbox.jobs_snapshot()
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["attempts"] == 1
    assert state.snapshot()["s3"]["data.json"]["status"] == "failed"
