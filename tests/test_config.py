import pytest

from nsdf_storage_service.config import (
    build_client_config,
    get_source_event_config,
    hierarchy_dict_to_dot,
)


def _base_config():
    return {
        "intersect": {
            "brokers": [
                {
                    "username": "intersect_username",
                    "password": "intersect_password",
                    "host": "127.0.0.1",
                    "port": 5672,
                    "protocol": "amqp0.9.1",
                }
            ]
        },
        "intersect-hierarchy": {
            "organization": "chess",
            "facility": "chess-facility",
            "system": "storage-system",
            "subsystem": "storage-subsystem",
            "service": "nsdf-storage-service",
        },
        "source-event": {
            "hierarchy": {
                "organization": "chess",
                "facility": "chess-facility",
                "system": "data-egress-system",
                "subsystem": "data-egress-subsystem",
                "service": "chess-data-egress-service",
            },
            "capability": "chess_data_egress",
            "event": "new_measurement",
        },
    }


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


def test_get_source_event_config_uses_expected_defaults():
    raw_config = {"intersect": {"brokers": []}}

    assert get_source_event_config(raw_config) == {
        "hierarchy": (
            "chess.chess-facility.data-egress-system."
            "data-egress-subsystem.chess-data-egress-service"
        ),
        "capability": "chess_data_egress",
        "event": "new_measurement",
    }


def test_build_client_config_subscribes_to_new_measurement():
    config = build_client_config(_base_config())
    event_config = config.initial_message_event_config.services_to_start_listening_for_events[0]

    assert event_config.hierarchy == (
        "chess.chess-facility.data-egress-system.data-egress-subsystem.chess-data-egress-service"
    )
    assert event_config.capability_name == "chess_data_egress"
    assert event_config.event_name == "new_measurement"


def test_build_client_config_requires_brokers():
    with pytest.raises(ValueError, match="brokers"):
        build_client_config({})
