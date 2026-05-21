import json
from unittest.mock import patch

import pytest

import nsdf_storage_service.endpoints as _endpoints_mod
from nsdf_storage_service import s3_uploader


@pytest.fixture(autouse=True)
def _reset_state():
    acc = _endpoints_mod._accumulator
    acc._measurements["labx"].clear()
    acc._measurements["labz"].clear()
    acc._measurements["center_value"].clear()
    acc._initialized = False
    yield


@pytest.fixture(autouse=True)
def _patch_upload():
    with patch("nsdf_storage_service.s3_uploader.upload_file") as mock:
        yield mock


def test_new_measurement_creates_data_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )

    output_file = tmp_path / "data.json"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data == {
        "labx": [1.0],
        "labz": [2.0],
        "center_value": [3.0],
    }
    _patch_upload.assert_called_once_with("data.json")


def test_new_measurement_appends_values(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )
    _endpoints_mod.new_measurement(
        source="src2",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 4.0, "labz": 5.0, "center_value": 6.0},
    )

    data = json.loads((tmp_path / "data.json").read_text())
    assert data == {
        "labx": [1.0, 4.0],
        "labz": [2.0, 5.0],
        "center_value": [3.0, 6.0],
    }
    assert _patch_upload.call_count == 2


def test_new_measurement_recovers_from_existing_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path
    tmp_path.mkdir(parents=True, exist_ok=True)
    existing = tmp_path / "data.json"
    existing.write_text(
        json.dumps({"labx": [1.0, 2.0], "labz": [3.0, 4.0], "center_value": [5.0, 6.0]})
    )

    _endpoints_mod.new_measurement(
        source="src3",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 7.0, "labz": 8.0, "center_value": 9.0},
    )

    data = json.loads((tmp_path / "data.json").read_text())
    assert data == {
        "labx": [1.0, 2.0, 7.0],
        "labz": [3.0, 4.0, 8.0],
        "center_value": [5.0, 6.0, 9.0],
    }


def test_new_measurement_logs_on_bad_payload(caplog, _patch_upload):
    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload="not a dict",
    )

    assert "Unexpected payload type" in caplog.text
