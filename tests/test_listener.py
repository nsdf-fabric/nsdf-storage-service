import json
from unittest.mock import patch

import pytest

import nsdf_storage_service.endpoints as _endpoints_mod
from nsdf_storage_service import s3_uploader


@pytest.fixture(autouse=True)
def _patch_upload():
    with patch("nsdf_storage_service.s3_uploader.upload_file") as mock:
        yield mock


def test_new_measurement_creates_data_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path
    payload = {
        "dataset_x": [[1.0, 2.0], [3.0, 4.0]],
        "dataset_y": [69.1, 69.2],
        "backend": "sklearn",
        "kernel": "rbf",
        "bounds": [[0.0, 10.0], [0.0, 10.0]],
        "dim_x": 2,
    }

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload=payload,
    )

    output_file = tmp_path / "data.json"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data["dataset_x"] == payload["dataset_x"]
    assert data["dataset_y"] == payload["dataset_y"]
    assert data["backend"] == payload["backend"]
    assert data["kernel"] == payload["kernel"]
    assert data["bounds"] == payload["bounds"]
    _patch_upload.assert_called_once_with("data.json", dataset_x_size=None)


def test_new_measurement_persists_and_uploads_explicit_dataset_x_size(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path
    payload = {
        "dataset_x": [[1.0, 2.0], [3.0, 4.0]],
        "dataset_y": [69.1, 69.2],
        "dataset_x_size": 8,
        "backend": "sklearn",
        "kernel": "rbf",
        "bounds": [[0.0, 10.0], [0.0, 10.0]],
        "dim_x": 2,
    }

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload=payload,
    )

    data = json.loads((tmp_path / "data.json").read_text())
    assert data["dataset_x_size"] == 8
    _patch_upload.assert_called_once_with("data.json", dataset_x_size=8)


def test_new_measurement_does_not_infer_dataset_x_size(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={
            "dataset_x": [[1.0, 2.0], [3.0, 4.0]],
            "dataset_y": [69.1, 69.2],
            "backend": "sklearn",
            "kernel": "rbf",
            "bounds": [[0.0, 10.0], [0.0, 10.0]],
            "dim_x": 2,
        },
    )

    data = json.loads((tmp_path / "data.json").read_text())
    assert "dataset_x_size" not in data
    _patch_upload.assert_called_once_with("data.json", dataset_x_size=None)


def test_new_measurement_overwrites_data_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={
            "dataset_x": [[1.0, 2.0]],
            "dataset_y": [69.1],
            "backend": "sklearn",
            "kernel": "rbf",
            "bounds": [[0.0, 10.0], [0.0, 10.0]],
            "dim_x": 2,
        },
    )
    _endpoints_mod.new_measurement(
        source="src2",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={
            "dataset_x": [[3.0, 4.0], [5.0, 6.0]],
            "dataset_y": [69.2, 69.3],
            "backend": "sklearn",
            "kernel": "rbf",
            "bounds": [[0.0, 10.0], [0.0, 10.0]],
            "dim_x": 2,
        },
    )

    data = json.loads((tmp_path / "data.json").read_text())
    assert data["dataset_x"] == [[3.0, 4.0], [5.0, 6.0]]
    assert data["dataset_y"] == [69.2, 69.3]
    assert _patch_upload.call_count == 2


def test_new_measurement_logs_on_bad_payload(caplog, _patch_upload):
    _endpoints_mod.new_measurement(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload="not a dict",
    )

    assert "Unexpected payload type" in caplog.text
    _patch_upload.assert_not_called()


def test_next_point_creates_next_x_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0]},
    )

    output_file = tmp_path / "next_x.json"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data == {"workflow_id": "workflow-1", "data": [[1.0, 2.0]]}
    _patch_upload.assert_called_once_with("next_x.json", dataset_x_size=None)


def test_next_point_persists_and_uploads_explicit_dataset_x_size(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0], "dataset_x_size": 4},
    )

    data = json.loads((tmp_path / "next_x.json").read_text())
    assert data == {"workflow_id": "workflow-1", "data": [[1.0, 2.0]], "dataset_x_size": 4}
    _patch_upload.assert_called_once_with("next_x.json", dataset_x_size=4)


def test_next_point_overwrites_matching_workflow(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0]},
    )
    _endpoints_mod.next_point(
        source="src2",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [3.0, 4.0]},
    )

    data = json.loads((tmp_path / "next_x.json").read_text())
    assert data == {"workflow_id": "workflow-1", "data": [[3.0, 4.0]]}
    assert _patch_upload.call_count == 2


def test_next_point_overwrites_dataset_x_size_for_matching_workflow(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0], "dataset_x_size": 3},
    )
    _endpoints_mod.next_point(
        source="src2",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [3.0, 4.0], "dataset_x_size": 4},
    )

    data = json.loads((tmp_path / "next_x.json").read_text())
    assert data == {
        "workflow_id": "workflow-1",
        "data": [[3.0, 4.0]],
        "dataset_x_size": 4,
    }
    assert _patch_upload.call_args_list[-1].kwargs == {"dataset_x_size": 4}


def test_next_point_overwrites_with_new_workflow(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-1", "data": [1.0, 2.0]},
    )
    _endpoints_mod.next_point(
        source="src2",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload={"workflow_id": "workflow-2", "data": [5.0, 6.0]},
    )

    data = json.loads((tmp_path / "next_x.json").read_text())
    assert data == {"workflow_id": "workflow-2", "data": [[5.0, 6.0]]}
    assert _patch_upload.call_count == 2


def test_surrogate_values_creates_surrogate_file(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.surrogate_values(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="surrogate_values",
        payload={
            "workflow_id": "workflow-1",
            "data": [[1.0, 2.0], [0.1, 0.2], [0.01, 0.02]],
        },
    )

    output_file = tmp_path / "surrogate.json"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data == {
        "workflow_id": "workflow-1",
        "surrogate": [1.0, 2.0],
        "uncertainty": [0.1, 0.2],
        "raw_uncertainty": [0.01, 0.02],
    }
    _patch_upload.assert_called_once_with("surrogate.json", dataset_x_size=None)


def test_surrogate_values_can_omit_raw_uncertainty(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.surrogate_values(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="surrogate_values",
        payload={"workflow_id": "workflow-1", "data": [[1.0, 2.0], [0.1, 0.2]]},
    )

    data = json.loads((tmp_path / "surrogate.json").read_text())
    assert data == {
        "workflow_id": "workflow-1",
        "surrogate": [1.0, 2.0],
        "uncertainty": [0.1, 0.2],
    }
    _patch_upload.assert_called_once_with("surrogate.json", dataset_x_size=None)


def test_surrogate_values_accepts_expanded_dial_payload(tmp_path, _patch_upload):
    s3_uploader._uploader._data_dir = tmp_path

    _endpoints_mod.surrogate_values(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="surrogate_values",
        payload={
            "workflow_id": "workflow-1",
            "dataset_x_size": 5,
            "values": [1.0, 2.0],
            "transformed_stddevs": [0.1, 0.2],
            "transformed_stddevs_avg": 0.15,
            "stddevs": [0.01, 0.02],
            "dim_x": 2,
            "bounds": [[24.0, 0.0], [0.0, 24.0]],
            "points_to_predict": [[1.0, 2.0], [3.0, 4.0]],
        },
    )

    data = json.loads((tmp_path / "surrogate.json").read_text())
    assert data == {
        "workflow_id": "workflow-1",
        "dataset_x_size": 5,
        "transformed_stddevs_avg": 0.15,
        "surrogate": [1.0, 2.0],
        "uncertainty": [0.1, 0.2],
        "raw_uncertainty": [0.01, 0.02],
        "dim_x": 2,
        "bounds": [[0.0, 24.0], [0.0, 24.0]],
        "points_to_predict": [[1.0, 2.0], [3.0, 4.0]],
    }
    _patch_upload.assert_called_once_with("surrogate.json", dataset_x_size=5)


def test_dial_handlers_log_on_bad_payload(caplog, _patch_upload):
    _endpoints_mod.next_point(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="next_point",
        payload="not a dict",
    )
    _endpoints_mod.surrogate_values(
        source="src1",
        capability_name="nsdf_storage",
        endpoint_name="surrogate_values",
        payload={"workflow_id": "workflow-1", "data": [[1.0, 2.0]]},
    )

    assert "Unexpected next_point payload type" in caplog.text
    assert "Received surrogate_values payload that does not match expected model" in caplog.text
    _patch_upload.assert_not_called()
