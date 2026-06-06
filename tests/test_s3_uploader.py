from unittest.mock import Mock, patch
from datetime import datetime, timezone

from nsdf_storage_service.s3_uploader import S3Uploader


def test_init_s3_applies_data_dir_when_s3_is_disabled(tmp_path):
    data_dir = tmp_path / "configured-data"
    uploader = S3Uploader()

    uploader.init_s3({"data_dir": str(data_dir)})

    assert uploader._data_dir == data_dir
    assert data_dir.exists()


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


def test_upload_file_returns_true_uploads_stable_and_timestamped_data(tmp_path):
    local_file = tmp_path / "data.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path
    now = datetime(2026, 6, 6, 14, 30, 12, tzinfo=timezone.utc)

    with (
        patch("nsdf_storage_service.s3_uploader.datetime") as datetime_mock,
        patch("nsdf_storage_service.refresh_notifier.notify_refresh") as notify_mock,
    ):
        datetime_mock.now.return_value = now
        assert uploader.upload_file("data.json") is True

    assert uploader._client.upload_file.call_args_list == [
        ((str(local_file), "bucket", "prefix/data.json"),),
        ((str(local_file), "bucket", "prefix/data_20260606T143012Z.json"),),
    ]
    notify_mock.assert_called_once_with()


def test_upload_file_uses_matching_timestamped_name_for_surrogate(tmp_path):
    local_file = tmp_path / "surrogate.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path
    now = datetime(2026, 6, 6, 14, 30, 12, tzinfo=timezone.utc)

    with (
        patch("nsdf_storage_service.s3_uploader.datetime") as datetime_mock,
        patch("nsdf_storage_service.refresh_notifier.notify_refresh"),
    ):
        datetime_mock.now.return_value = now
        assert uploader.upload_file("surrogate.json") is True

    assert uploader._client.upload_file.call_args_list == [
        ((str(local_file), "bucket", "prefix/surrogate.json"),),
        ((str(local_file), "bucket", "prefix/surrogate_20260606T143012Z.json"),),
    ]


def test_upload_file_uses_matching_timestamped_name_for_next_x(tmp_path):
    local_file = tmp_path / "next_x.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path
    now = datetime(2026, 6, 6, 14, 30, 12, tzinfo=timezone.utc)

    with (
        patch("nsdf_storage_service.s3_uploader.datetime") as datetime_mock,
        patch("nsdf_storage_service.refresh_notifier.notify_refresh"),
    ):
        datetime_mock.now.return_value = now
        assert uploader.upload_file("next_x.json") is True

    assert uploader._client.upload_file.call_args_list == [
        ((str(local_file), "bucket", "prefix/next_x.json"),),
        ((str(local_file), "bucket", "prefix/next_x_20260606T143012Z.json"),),
    ]


def test_upload_file_returns_false_and_does_not_notify_on_stable_s3_error(tmp_path):
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


def test_upload_file_returns_false_and_does_not_notify_on_timestamped_s3_error(tmp_path):
    local_file = tmp_path / "data.json"
    local_file.write_text("{}\n")
    uploader = S3Uploader()
    uploader._client = Mock()
    uploader._client.upload_file.side_effect = [None, RuntimeError("boom")]
    uploader._bucket = "bucket"
    uploader._prefix = "prefix"
    uploader._data_dir = tmp_path

    with patch("nsdf_storage_service.refresh_notifier.notify_refresh") as notify_mock:
        assert uploader.upload_file("data.json") is False

    assert uploader._client.upload_file.call_count == 2
    notify_mock.assert_not_called()
