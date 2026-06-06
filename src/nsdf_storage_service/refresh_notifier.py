from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


DEFAULT_SCHEME = "http"
DEFAULT_PATH = "/refresh"
DEFAULT_TIMEOUT_SECONDS = 5


@dataclass
class RefreshConfig:
    host: str = ""
    port: int | None = None
    path: str = DEFAULT_PATH
    api_key: str = ""
    scheme: str = DEFAULT_SCHEME
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_dict(cls, config: dict) -> "RefreshConfig":
        return cls(
            host=str(config.get("host") or ""),
            port=config.get("port"),
            path=str(config.get("path") or DEFAULT_PATH),
            api_key=str(config.get("api_key") or ""),
            scheme=str(config.get("scheme") or DEFAULT_SCHEME),
            timeout_seconds=float(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.api_key)

    @property
    def url(self) -> str:
        host = self.host.strip()
        scheme = self.scheme.strip() or DEFAULT_SCHEME
        raw_path = self.path.strip() or DEFAULT_PATH
        path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
        encoded_path = quote(path, safe="/")
        netloc = f"{host}:{self.port}" if self.port else host
        return f"{scheme}://{netloc}{encoded_path}"


class RefreshNotifier:
    def __init__(self) -> None:
        self._config = RefreshConfig()

    def init_refresh(self, config: dict) -> None:
        self._config = RefreshConfig.from_dict(config)
        if self._config.enabled:
            logger.info("Refresh notifier initialized for %s", self._config.url)
        else:
            logger.info("Refresh notifier disabled")

    def notify_refresh(self) -> None:
        if not self._config.enabled:
            logger.debug("Refresh notifier is disabled; skipping refresh call")
            return

        request = Request(
            self._config.url,
            method="POST",
            headers={"X-API-Key": self._config.api_key},
        )

        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                response.read()
            logger.info("Refresh endpoint notified: %s", self._config.url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            logger.exception("Failed to notify refresh endpoint: %s", self._config.url)


_notifier = RefreshNotifier()


def init_refresh(config: dict) -> None:
    """Initialize refresh notification config."""
    _notifier.init_refresh(config)


def notify_refresh() -> None:
    """Notify the configured refresh endpoint."""
    _notifier.notify_refresh()
