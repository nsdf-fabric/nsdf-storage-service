import json

import pytest

from nsdf_storage_service.config import CONFIG_ENV_VAR, hierarchy_dict_to_dot, load_config


def test_load_config_reads_storage_service_config_env(monkeypatch):
    config = {
        "intersect": {"brokers": []},
        "intersect-hierarchy": {"organization": "chess"},
    }
    monkeypatch.setenv(CONFIG_ENV_VAR, json.dumps(config))

    assert load_config("missing.json") == config


def test_load_config_falls_back_to_file_when_env_is_unset(tmp_path, monkeypatch):
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"intersect": {"brokers": []}}\n')

    assert load_config(config_path) == {"intersect": {"brokers": []}}


def test_load_config_reports_invalid_storage_service_config(monkeypatch):
    monkeypatch.setenv(CONFIG_ENV_VAR, "{not-json")

    with pytest.raises(ValueError, match=f"Invalid JSON in {CONFIG_ENV_VAR}"):
        load_config("missing.json")


def test_load_config_requires_env_config_to_be_json_object(monkeypatch):
    monkeypatch.setenv(CONFIG_ENV_VAR, "[]")

    with pytest.raises(ValueError, match=f"{CONFIG_ENV_VAR} must contain a JSON object"):
        load_config("missing.json")


def test_hierarchy_dict_to_dot():
    hierarchy = {
        "organization": "chess",
        "facility": "chess-facility",
        "system": "data-egress-system",
        "subsystem": "data-egress-subsystem",
        "service": "chess-data-egress-service",
    }

    assert (
        hierarchy_dict_to_dot(hierarchy)
        == "chess.chess-facility.data-egress-system.data-egress-subsystem.chess-data-egress-service"
    )


def test_hierarchy_dict_to_dot_reports_missing_keys():
    with pytest.raises(ValueError, match="Missing hierarchy keys"):
        hierarchy_dict_to_dot({"organization": "chess"})
