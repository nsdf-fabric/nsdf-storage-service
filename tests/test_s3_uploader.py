from unittest.mock import Mock, patch

from nsdf_storage_service.s3_uploader import S3Uploader


def test_upload_file_returns_false_when_s3_disabled(tmp_path):
    uploader = S3Uploader()
    uploader._data_dir = tmp_path

    assert uploader.upload_file("data.json") is False


def test_upload_file_returns_false_when_file_is_missing(tmp_path):
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._data_dir = tmp_path

    assert uploader.upload_file("data.json") is False
    uploader._client.upload_file.assert_not_called()


def test_upload_file_returns_true_and_notifies_after_success(tmp_path):
    local_file = tmp_path / "data.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path

    with patch("nsdf_storage_service.refresh_notifier.notify_refresh") as notify_mock:
        assert uploader.upload_file("data.json") is True

    uploader._client.upload_file.assert_called_once_with(
        str(local_file),
        "bucket",
        "prefix/data.json",
    )
    notify_mock.assert_called_once_with()


def test_upload_file_returns_false_and_does_not_notify_on_s3_error(tmp_path):
    local_file = tmp_path / "data.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._client.upload_file.side_effect = RuntimeError("boom")
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path

    with patch("nsdf_storage_service.refresh_notifier.notify_refresh") as notify_mock:
        assert uploader.upload_file("data.json") is False

    notify_mock.assert_not_called()
