import pytest

from nsdf_storage_service.config import hierarchy_dict_to_dot


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
