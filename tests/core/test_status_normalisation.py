"""Tests for canonical status code normalisation."""
from __future__ import annotations

from hype_frog.core.status_codes import (
    STATUS_CONNECTION_ERROR,
    STATUS_TIMEOUT,
    is_error_status,
    is_success_status,
    normalise_status_code,
)


def test_http_status_stays_int() -> None:
    assert normalise_status_code(404) == 404
    assert normalise_status_code("200") == 200


def test_timeout_normalises_and_is_error() -> None:
    assert normalise_status_code("Timeout") == STATUS_TIMEOUT
    assert is_error_status(STATUS_TIMEOUT) is True
    assert is_success_status(STATUS_TIMEOUT) is False


def test_connection_error_is_error_status() -> None:
    assert normalise_status_code("Connection Error") == STATUS_CONNECTION_ERROR
    assert is_error_status(STATUS_CONNECTION_ERROR) is True


def test_http_500_is_error() -> None:
    assert is_error_status(500) is True
    assert is_error_status(200) is False


def test_non_200_rule_covers_timeout() -> None:
    from hype_frog.rules.registry import get_summary_rules

    rule = next(r for r in get_summary_rules() if r.name == "Non-200 Status")
    assert rule.fn({"Status Code": STATUS_TIMEOUT}) is True
    assert rule.fn({"Status Code": 200}) is False
