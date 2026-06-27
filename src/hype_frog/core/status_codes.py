"""Canonical HTTP and transport-error status codes for crawl rows."""
from __future__ import annotations

from typing import Literal

StatusCode = int | str

STATUS_TIMEOUT: Literal["Timeout"] = "Timeout"
STATUS_DNS_ERROR: Literal["DNS Error"] = "DNS Error"
STATUS_CONNECTION_ERROR: Literal["Connection Error"] = "Connection Error"
STATUS_SSL_ERROR: Literal["SSL Error"] = "SSL Error"
STATUS_GENERIC_ERROR: Literal["Error"] = "Error"

KNOWN_ERROR_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_TIMEOUT,
        STATUS_DNS_ERROR,
        STATUS_CONNECTION_ERROR,
        STATUS_SSL_ERROR,
        STATUS_GENERIC_ERROR,
    }
)


def normalise_status_code(value: object) -> StatusCode | None:
    """Return ``int`` for HTTP codes or a canonical string for transport failures."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
        if numeric.is_integer():
            return int(numeric)
    except ValueError:
        pass
    lowered = text.lower()
    if lowered == "timeout":
        return STATUS_TIMEOUT
    if lowered in {"dns error", "dns_error"}:
        return STATUS_DNS_ERROR
    if lowered in {"connection error", "connection_error"}:
        return STATUS_CONNECTION_ERROR
    if lowered in {"ssl error", "ssl_error"}:
        return STATUS_SSL_ERROR
    if lowered.startswith("error:"):
        return STATUS_GENERIC_ERROR
    return text


def is_http_status(value: object) -> bool:
    return isinstance(normalise_status_code(value), int)


def is_error_status(value: object) -> bool:
    """True for HTTP 4xx/5xx and canonical transport-error strings."""
    normalised = normalise_status_code(value)
    if normalised is None:
        return False
    if isinstance(normalised, int):
        return normalised >= 400
    return str(normalised) in KNOWN_ERROR_STATUSES


def is_success_status(value: object) -> bool:
    normalised = normalise_status_code(value)
    return normalised == 200


def is_redirect_status(value: object) -> bool:
    normalised = normalise_status_code(value)
    return isinstance(normalised, int) and 300 <= normalised < 400


def status_as_int_or_none(value: object) -> int | None:
    normalised = normalise_status_code(value)
    return normalised if isinstance(normalised, int) else None
