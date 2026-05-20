from unittest.mock import patch

from nsdf_storage_service.listener import event_callback, handle_new_measurement


def test_handle_new_measurement_prints_json_payload(capsys):
    handle_new_measurement(
        source="source",
        capability_name="chess_data_egress",
        event_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )

    captured = capsys.readouterr()
    assert "new_measurement" in captured.out
    assert '"labx": 1.0' in captured.out
    assert '"labz": 2.0' in captured.out
    assert '"center_value": 3.0' in captured.out


def test_event_callback_delegates_and_keeps_listening():
    with patch("nsdf_storage_service.listener.handle_new_measurement") as mock_handler:
        result = event_callback(
            "source",
            "chess_data_egress",
            "new_measurement",
            {"labx": 1.0, "labz": 2.0, "center_value": 3.0},
        )

    mock_handler.assert_called_once_with(
        source="source",
        capability_name="chess_data_egress",
        event_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )
    assert result is None
