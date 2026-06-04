from nsdf_storage_service.live_state import (
    LiveStateStore,
    flatten_next_points,
    measurement_to_points,
)


def test_live_state_initial_snapshot_is_empty_and_copy_safe():
    state = LiveStateStore()
    snapshot = state.snapshot()

    assert snapshot["revision"] == 0
    assert snapshot["measurement"] is None
    assert snapshot["next_points"] == {"all": [], "latest": None}

    snapshot["s3"]["data.json"]["status"] = "failed"
    assert state.snapshot()["s3"]["data.json"]["status"] == "missing"


def test_live_state_updates_measurement_and_revisions():
    state = LiveStateStore()
    measurement = {"dataset_x": [[1.0, 2.0]], "dataset_y": [3.0]}

    snapshot = state.update_measurement(measurement)

    assert snapshot["revision"] == 1
    assert snapshot["measurement_revision"] == 1
    assert snapshot["measured_points"] == [{"labx": 1.0, "labz": 2.0, "center_value": 3.0}]


def test_live_state_updates_next_points_and_latest():
    state = LiveStateStore()
    next_x = [
        {"workflow_id": "w1", "data": [[1.0, 2.0], [3.0, 4.0]]},
        {"workflow_id": "w2", "data": [[5.0, 6.0]]},
    ]

    snapshot = state.update_next_x(next_x)

    assert snapshot["next_x_revision"] == 1
    assert len(snapshot["next_points"]["all"]) == 3
    assert snapshot["next_points"]["latest"] == {
        "workflow_id": "w2",
        "labx": 5.0,
        "labz": 6.0,
        "sequence": 1,
    }


def test_live_state_updates_surrogate_and_s3_status():
    state = LiveStateStore()

    state.update_surrogate({"workflow_id": "w1", "surrogate": [1.0], "uncertainty": [0.1]})
    snapshot = state.update_s3_status("surrogate.json", "failed", error="boom")

    assert snapshot["surrogate_revision"] == 1
    assert snapshot["s3"]["surrogate.json"]["status"] == "failed"
    assert snapshot["s3"]["surrogate.json"]["error"] == "boom"


def test_normalizers_are_dashboard_friendly():
    assert measurement_to_points({"dataset_x": [[1, 2]], "dataset_y": [3]}) == [
        {"labx": 1, "labz": 2, "center_value": 3}
    ]
    assert flatten_next_points([{"workflow_id": "w", "data": [[1, 2]]}]) == {
        "all": [{"workflow_id": "w", "labx": 1, "labz": 2, "sequence": 1}],
        "latest": {"workflow_id": "w", "labx": 1, "labz": 2, "sequence": 1},
    }
