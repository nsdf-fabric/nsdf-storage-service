from nsdf_storage_service.listener import handle_new_measurement


def test_handle_new_measurement_prints_json_payload(capsys):
    handle_new_measurement(
        source="source",
        capability_name="nsdf_storage",
        endpoint_name="new_measurement",
        payload={"labx": 1.0, "labz": 2.0, "center_value": 3.0},
    )

    captured = capsys.readouterr()
    assert "new_measurement" in captured.out
    assert '"labx": 1.0' in captured.out
    assert '"labz": 2.0' in captured.out
    assert '"center_value": 3.0' in captured.out
