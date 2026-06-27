"""Edge-case coverage for the shared URL identity helper."""

from __future__ import annotations

from hype_frog.core.url_normalization import normalize_url


def test_empty_and_none_inputs() -> None:
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_lowercases_host_but_preserves_path_case() -> None:
    assert normalize_url("https://Example.com/Path/") == "https://example.com/Path"
    assert normalize_url("https://WWW.E.COM/A") == "https://www.e.com/A"


def test_uppercase_scheme_is_passed_through_verbatim() -> None:
    # The scheme check is case-sensitive, so an upper-case scheme is treated as
    # non-HTTP and returned as-is (only the trailing slash is stripped).
    assert normalize_url("HTTP://E.COM/A/") == "HTTP://E.COM/A"


def test_root_path_normalises_to_single_slash() -> None:
    assert normalize_url("https://example.com") == "https://example.com/"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_query_kept_by_default_and_dropped_when_requested() -> None:
    assert normalize_url("https://e.com/a?b=1&c=2") == "https://e.com/a?b=1&c=2"
    assert normalize_url("https://e.com/a?b=1&c=2", keep_query=False) == "https://e.com/a"


def test_non_http_scheme_returned_verbatim_without_trailing_slash() -> None:
    assert normalize_url("mailto:x@y.com") == "mailto:x@y.com"
    assert normalize_url("/relative/path/") == "/relative/path"


def test_trailing_slash_stripped_for_deep_paths() -> None:
    assert normalize_url("https://e.com/a/b/c/") == "https://e.com/a/b/c"
