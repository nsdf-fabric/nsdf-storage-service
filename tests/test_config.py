import pytest

from nsdf_storage_service.config import (
    CONFIG_JSON_ENV_VAR,
    hierarchy_dict_to_dot,
    load_runtime_config,
)


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


def test_load_runtime_config_falls_back_to_file(tmp_path, monkeypatch):
    monkeypatch.delenv(CONFIG_JSON_ENV_VAR, raising=False)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"source": "file"}')

    assert load_runtime_config(config_path) == {"source": "file"}


def test_load_runtime_config_uses_env_json(monkeypatch):
    monkeypatch.setenv(CONFIG_JSON_ENV_VAR, '{"source": "env"}')

    assert load_runtime_config("missing.json") == {"source": "env"}


def test_load_runtime_config_env_json_takes_precedence(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"source": "file"}')
    monkeypatch.setenv(CONFIG_JSON_ENV_VAR, '{"source": "env"}')

    assert load_runtime_config(config_path) == {"source": "env"}


def test_load_runtime_config_reports_invalid_env_json(monkeypatch):
    monkeypatch.setenv(CONFIG_JSON_ENV_VAR, "{not-json")

    with pytest.raises(ValueError, match=CONFIG_JSON_ENV_VAR):
        load_runtime_config("local-conf.json")


def test_load_runtime_config_requires_env_json_object(monkeypatch):
    monkeypatch.setenv(CONFIG_JSON_ENV_VAR, '["not", "an", "object"]')

    with pytest.raises(ValueError, match="JSON object"):
        load_runtime_config("local-conf.json")
