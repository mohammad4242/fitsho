from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from urllib.parse import urlsplit


class ProxySource(StrEnum):
    DEPLOYMENT_DEFAULT = "deployment_default"
    CUSTOM = "custom"


class ProxyConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ProxyRuntimeStatus:
    enabled: bool
    source: ProxySource
    configured: bool
    default_configured: bool
    masked_proxy_url: str | None


_PROXY_ENVIRONMENT_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_DEFAULT_PROXY_STATUS_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_PROXY_SCHEMES = frozenset({"http", "https", "socks5", "socks5h"})


def validate_proxy_url(value: str) -> str:
    candidate = value.strip()
    if not candidate or any(character.isspace() for character in candidate):
        raise ProxyConfigurationError("proxy URL must be a non-empty URL")
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        _parsed_port = parsed.port
    except ValueError as error:
        raise ProxyConfigurationError("proxy URL is invalid") from error
    if parsed.scheme.lower() not in _PROXY_SCHEMES or not hostname:
        raise ProxyConfigurationError("proxy URL must use a supported proxy scheme")
    return candidate


def mask_proxy_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if not hostname:
            return None
        host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        port = f":{parsed.port}" if parsed.port is not None else ""
        credentials = (
            "****:****@"
            if parsed.username is not None or parsed.password is not None
            else ""
        )
        return f"{parsed.scheme.lower()}://{credentials}{host}{port}"
    except (TypeError, ValueError):
        return None


class ProxyRuntime:
    """Thread-safe runtime proxy state shared by runners and auth processes."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        base_environment = dict(os.environ if environment is None else environment)
        self._base_environment = base_environment
        self._default_proxy_values = {
            key: value.strip()
            for key, value in base_environment.items()
            if key in _PROXY_ENVIRONMENT_KEYS and isinstance(value, str) and value.strip()
        }
        self._enabled = True
        self._source = ProxySource.DEPLOYMENT_DEFAULT
        self._custom_proxy_url: str | None = None
        self._lock = RLock()

    def apply(self, environment: Mapping[str, str]) -> dict[str, str]:
        result = dict(environment)
        for key in _PROXY_ENVIRONMENT_KEYS:
            result.pop(key, None)
        with self._lock:
            if self._enabled:
                if self._source is ProxySource.CUSTOM:
                    assert self._custom_proxy_url is not None
                    result["HTTP_PROXY"] = self._custom_proxy_url
                    result["HTTPS_PROXY"] = self._custom_proxy_url
                else:
                    result.update(self._default_proxy_values)
        return result

    def environment(self) -> dict[str, str]:
        return self.apply(self._base_environment)

    def status(self) -> ProxyRuntimeStatus:
        with self._lock:
            selected_url = (
                self._custom_proxy_url
                if self._source is ProxySource.CUSTOM
                else next(
                    (
                        self._default_proxy_values[key]
                        for key in _DEFAULT_PROXY_STATUS_KEYS
                        if key in self._default_proxy_values
                    ),
                    None,
                )
            )
            default_configured = any(self._default_proxy_values.values())
            return ProxyRuntimeStatus(
                enabled=self._enabled,
                source=self._source,
                configured=bool(selected_url),
                default_configured=default_configured,
                masked_proxy_url=mask_proxy_url(selected_url),
            )

    def update(
        self,
        *,
        enabled: bool,
        source: ProxySource,
        proxy_url: str | None = None,
    ) -> ProxyRuntimeStatus:
        if source is ProxySource.CUSTOM:
            if proxy_url is None and enabled:
                raise ProxyConfigurationError("custom proxy URL is required")
            if proxy_url is not None:
                proxy_url = validate_proxy_url(proxy_url)
        elif proxy_url is not None:
            raise ProxyConfigurationError("deployment default cannot include a custom URL")
        with self._lock:
            self._enabled = enabled
            self._source = source
            if proxy_url is not None:
                self._custom_proxy_url = proxy_url
        return self.status()
