import json

from fastapi.testclient import TestClient

from nsdf_storage_service.web_app import create_app


def _config(tmp_path):
    return {
        "intersect": {"brokers": []},
        "intersect-hierarchy": {
            "organization": "chess",
            "facility": "chess-facility",
            "system": "storage-system",
            "subsystem": "storage-subsystem",
            "service": "nsdf-storage-service",
        },
        "s3": {"data_dir": str(tmp_path), "aws_access_key_id": "", "aws_secret_access_key": ""},
        "dashboard": {"grid_size": [11, 7]},
    }


def test_fastapi_health_state_meta_and_raw_json(tmp_path):
    config_path = tmp_path / "conf.json"
    config_path.write_text(json.dumps(_config(tmp_path)))
    (tmp_path / "data.json").write_text(json.dumps({"dataset_x": [[1.0, 2.0]], "dataset_y": [3.0]}))

    with TestClient(create_app(config_path=config_path, start_intersect=False)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        state = client.get("/api/state").json()
        assert state["measurement"]["dataset_y"] == [3.0]
        assert state["dashboard"]["measured_points"][0]["center_value"] == 3.0
        assert state["dashboard_config"]["grid_size"] == [11, 7]
        assert state["dashboard_config"]["grid_bounds"] == [[0, 11], [0, 7]]
        assert client.get("/api/meta").json()["revision"] >= 1
        assert client.get("/api/data.json").json()["dataset_y"] == [3.0]


def test_fastapi_websocket_receives_initial_snapshot(tmp_path):
    config_path = tmp_path / "conf.json"
    config_path.write_text(json.dumps(_config(tmp_path)))

    with TestClient(create_app(config_path=config_path, start_intersect=False)) as client:
        with client.websocket_connect("/ws/state") as websocket:
            event = websocket.receive_json()

    assert event["type"] == "state_snapshot"
    assert event["state"]["revision"] == 0
    assert event["state"]["dashboard_config"]["grid_size"] == [11, 7]
    assert event["state"]["dashboard_config"]["grid_bounds"] == [[0, 11], [0, 7]]


def test_fastapi_can_load_config_from_env_json(tmp_path, monkeypatch):
    monkeypatch.setenv("NSDF_STORAGE_SERVICE_CONFIG_JSON", json.dumps(_config(tmp_path)))

    with TestClient(
        create_app(config_path=tmp_path / "does-not-exist.json", start_intersect=False)
    ) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/state").json()["dashboard_config"]["grid_size"] == [11, 7]
