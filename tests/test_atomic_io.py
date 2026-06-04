import json

from nsdf_storage_service.atomic_io import write_json_atomic


def test_write_json_atomic_creates_valid_json_and_removes_temp(tmp_path):
    path = tmp_path / "data.json"

    write_json_atomic(path, {"value": [1, 2, 3]})

    assert json.loads(path.read_text()) == {"value": [1, 2, 3]}
    assert not (tmp_path / ".data.json.tmp").exists()
