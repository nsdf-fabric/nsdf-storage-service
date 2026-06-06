from unittest.mock import Mock, patch
from urllib.error import URLError

from nsdf_storage_service.refresh_notifier import RefreshConfig, RefreshNotifier


def test_refresh_config_is_disabled_without_host():
    config = RefreshConfig.from_dict({"api_key": "secret"})

    assert config.enabled is False


def test_refresh_config_is_disabled_without_api_key():
    config = RefreshConfig.from_dict({"host": "localhost"})

    assert config.enabled is False


def test_refresh_config_builds_url_from_parts():
    config = RefreshConfig.from_dict(
        {
            "scheme": "http",
            "host": "localhost",
            "port": 8060,
            "path": "refresh",
            "api_key": "secret",
        }
    )

    assert config.enabled is True
    assert config.url == "http://localhost:8060/refresh"


def test_notify_refresh_sends_post_with_api_key():
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b""
    notifier = RefreshNotifier()
    notifier.init_refresh(
        {
            "host": "localhost",
            "port": 8060,
            "path": "/refresh",
            "api_key": "secret",
            "timeout_seconds": 7,
        }
    )

    with patch("nsdf_storage_service.refresh_notifier.urlopen", return_value=response) as open_mock:
        notifier.notify_refresh()

    request = open_mock.call_args.args[0]
    assert request.full_url == "http://localhost:8060/refresh"
    assert request.get_method() == "POST"
    assert request.headers["X-api-key"] == "secret"
    assert open_mock.call_args.kwargs["timeout"] == 7


def test_notify_refresh_logs_and_continues_on_error(caplog):
    notifier = RefreshNotifier()
    notifier.init_refresh({"host": "localhost", "api_key": "secret"})

    with patch(
        "nsdf_storage_service.refresh_notifier.urlopen",
        side_effect=URLError("connection refused"),
    ):
        notifier.notify_refresh()

    assert "Failed to notify refresh endpoint" in caplog.text
    assert "secret" not in caplog.text
