"""Tests for `crawler/gsc_engine.py` beyond OAuth path resolution.

`tests/crawler/test_gsc_auth_paths.py` already covers `resolve_gsc_credentials_path`
/`resolve_gsc_token_path`. Before this file, the rest of the module — URL/host
helpers, the Search Analytics row mapper, the URL Inspection SQLite cache, and
the offline (no-credentials) early-exit branches of `load_gsc_enrichment_context`,
`load_gsc_credentials_readonly`, and `probe_gsc_api_access` — had no direct
coverage; only 2 of ~24 defs in this file were directly tested.

No live Google API calls are made anywhere in this file — every test either
exercises a pure helper or an offline early-exit branch, or supplies a fake
``service`` object standing in for the googleapiclient resource.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hype_frog.crawler import gsc_engine


# ---------------------------------------------------------------------------
# Pure URL/host helpers
# ---------------------------------------------------------------------------

def test_normalize_url_strips_trailing_slash_and_whitespace() -> None:
    assert gsc_engine._normalize_url("  https://example.com/page/  ") == "https://example.com/page"


def test_normalize_url_handles_none_and_empty() -> None:
    assert gsc_engine._normalize_url("") == ""
    assert gsc_engine._normalize_url(None) == ""  # type: ignore[arg-type]


def test_extract_host_from_full_url() -> None:
    assert gsc_engine._extract_host("https://www.example.com/page") == "www.example.com"


def test_extract_host_lowercases_result() -> None:
    assert gsc_engine._extract_host("https://EXAMPLE.com/") == "example.com"


def test_extract_host_falls_back_to_bare_domain() -> None:
    assert gsc_engine._extract_host("example.com/page") == "example.com"


def test_extract_host_empty_for_unparseable_input() -> None:
    assert gsc_engine._extract_host("") == ""


def test_build_candidate_site_urls_includes_domain_and_www_variants() -> None:
    candidates = gsc_engine._build_candidate_site_urls("https://www.example.com/")
    assert candidates == [
        "sc-domain:example.com",
        "https://example.com/",
        "http://example.com/",
        "https://www.example.com/",
        "http://www.example.com/",
    ]


def test_build_candidate_site_urls_empty_for_hostless_input() -> None:
    assert gsc_engine._build_candidate_site_urls("") == []


# ---------------------------------------------------------------------------
# _rows_to_page_metrics / _inspection_error_fields
# ---------------------------------------------------------------------------

def test_rows_to_page_metrics_maps_clicks_impressions_ctr_position() -> None:
    rows = [
        {
            "keys": ["https://example.com/page/"],
            "clicks": 12,
            "impressions": 340,
            "ctr": 0.035,
            "position": 8.2,
        }
    ]
    metrics = gsc_engine._rows_to_page_metrics(rows)
    entry = metrics["https://example.com/page/"]
    assert entry == {
        "GSC Clicks": 12.0,
        "GSC Impressions": 340.0,
        "GSC CTR": 0.035,
        "GSC Average Position": 8.2,
    }


def test_rows_to_page_metrics_keys_by_both_raw_and_normalized_url() -> None:
    rows = [{"keys": ["https://example.com/page/"], "clicks": 1, "impressions": 1, "ctr": 1, "position": 1}]
    metrics = gsc_engine._rows_to_page_metrics(rows)
    assert "https://example.com/page/" in metrics
    assert "https://example.com/page" in metrics  # normalized (no trailing slash)


def test_rows_to_page_metrics_skips_rows_without_a_page_key() -> None:
    rows = [{"keys": [], "clicks": 1, "impressions": 1, "ctr": 1, "position": 1}]
    assert gsc_engine._rows_to_page_metrics(rows) == {}


def test_rows_to_page_metrics_empty_input() -> None:
    assert gsc_engine._rows_to_page_metrics([]) == {}


def test_inspection_error_fields_marks_coverage_as_error() -> None:
    fields = gsc_engine._inspection_error_fields()
    assert fields["GSC Inspection Coverage"] == "Error"
    assert fields["GSC Inspection Verdict"] is None
    assert set(fields.keys()) == {
        "GSC Inspection Coverage",
        "GSC Inspection Verdict",
        "GSC Inspection Coverage State",
        "GSC Inspection Google Canonical",
        "GSC Inspection Crawl State",
        "GSC Inspection Robots State",
        "GSC Inspection Last Crawl",
        "GSC Index Status",
        "GSC Last Crawl Date",
        "GSC Mobile Usability",
        "GSC Rich Result Status",
        "GSC Coverage Reason",
        "Days Since Last Crawl",
    }


# ---------------------------------------------------------------------------
# _resolve_site_url (fake service — no live API)
# ---------------------------------------------------------------------------

class _FakeSitesResource:
    def __init__(self, site_entries: list[dict[str, str]]) -> None:
        self._site_entries = site_entries

    def list(self) -> "_FakeSitesResource":
        return self

    def execute(self) -> dict[str, object]:
        return {"siteEntry": self._site_entries}


class _FakeService:
    def __init__(self, site_entries: list[dict[str, str]]) -> None:
        self._sites = _FakeSitesResource(site_entries)

    def sites(self) -> _FakeSitesResource:
        return self._sites


def test_resolve_site_url_matches_domain_property() -> None:
    service = _FakeService([{"siteUrl": "sc-domain:example.com"}])
    assert gsc_engine._resolve_site_url(service, "https://example.com/") == "sc-domain:example.com"


def test_resolve_site_url_matches_url_prefix_property() -> None:
    service = _FakeService([{"siteUrl": "https://example.com/"}])
    assert gsc_engine._resolve_site_url(service, "https://www.example.com/page") == "https://example.com/"


def test_resolve_site_url_returns_none_when_no_candidate_matches() -> None:
    service = _FakeService([{"siteUrl": "sc-domain:other.com"}])
    assert gsc_engine._resolve_site_url(service, "https://example.com/") is None


def test_resolve_site_url_returns_none_on_api_error() -> None:
    class _BoomService:
        def sites(self) -> "_BoomService":
            return self

        def list(self) -> "_BoomService":
            return self

        def execute(self) -> None:
            raise RuntimeError("boom")

    assert gsc_engine._resolve_site_url(_BoomService(), "https://example.com/") is None


# ---------------------------------------------------------------------------
# load_gsc_credentials_readonly (offline: missing/malformed files, no network)
# ---------------------------------------------------------------------------

def test_load_gsc_credentials_readonly_missing_credentials_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    creds, error = gsc_engine.load_gsc_credentials_readonly()
    assert creds is None
    assert error is not None
    assert "Credentials file not found" in error


def test_load_gsc_credentials_readonly_missing_token_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "client_secrets.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", secrets)
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    creds, error = gsc_engine.load_gsc_credentials_readonly()
    assert creds is None
    assert error is not None
    assert "Token file not found" in error
    assert "--gsc-auth" in error


def test_load_gsc_credentials_readonly_malformed_token_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "client_secrets.json").write_text("{}", encoding="utf-8")
    (secrets / "token.json").write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", secrets)
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    creds, error = gsc_engine.load_gsc_credentials_readonly()
    assert creds is None
    assert error is not None
    assert "unreadable or malformed" in error


# ---------------------------------------------------------------------------
# probe_gsc_api_access (offline early-exit: no credentials)
# ---------------------------------------------------------------------------

def test_probe_gsc_api_access_fails_offline_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    ok, message, site_urls, matched = gsc_engine.probe_gsc_api_access("https://example.com/")
    assert ok is False
    assert "Credentials file not found" in message
    assert site_urls == []
    assert matched is None


# ---------------------------------------------------------------------------
# load_gsc_enrichment_context / fetch_gsc_page_metrics (offline early-exit)
# ---------------------------------------------------------------------------

def test_load_gsc_enrichment_context_returns_empty_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    ctx = gsc_engine.load_gsc_enrichment_context("https://example.com/")
    assert ctx.page_metrics == {}
    assert ctx.analytics_query_succeeded is False
    assert ctx.service is None
    assert ctx.site_url is None


def test_fetch_gsc_page_metrics_delegates_and_returns_empty_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(gsc_engine, "_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)

    assert gsc_engine.fetch_gsc_page_metrics("https://example.com/") == {}


# ---------------------------------------------------------------------------
# URL Inspection SQLite cache (mirrors psi_cache.py test pattern)
# ---------------------------------------------------------------------------

def test_inspection_cache_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)
    conn = gsc_engine._open_inspection_cache_db()
    try:
        assert gsc_engine._inspection_cache_get(conn, "https://example.com/") is None
        gsc_engine._inspection_cache_put(conn, "https://example.com/", {"verdict": "PASS"})
        assert gsc_engine._inspection_cache_get(conn, "https://example.com/") == {"verdict": "PASS"}
    finally:
        conn.close()


def test_inspection_cache_expires_stale_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)
    conn = gsc_engine._open_inspection_cache_db()
    try:
        stale_timestamp = time.time() - gsc_engine._CACHE_TTL_SECONDS - 1
        conn.execute(
            "INSERT INTO gsc_inspection_cache (inspection_url, response_body, fetched_at) "
            "VALUES (?, ?, ?)",
            ("https://example.com/stale", '{"verdict": "PASS"}', stale_timestamp),
        )
        conn.commit()
        assert gsc_engine._inspection_cache_get(conn, "https://example.com/stale") is None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# fetch_gsc_url_inspections_batch (early-return branches + one fake-service round trip)
# ---------------------------------------------------------------------------

def test_fetch_gsc_url_inspections_batch_empty_urls_returns_empty_dict() -> None:
    assert gsc_engine.fetch_gsc_url_inspections_batch(object(), "sc-domain:example.com", []) == {}


def test_fetch_gsc_url_inspections_batch_none_service_returns_empty_dict() -> None:
    assert gsc_engine.fetch_gsc_url_inspections_batch(None, "sc-domain:example.com", ["https://example.com/"]) == {}


def test_fetch_gsc_url_inspections_batch_empty_site_url_returns_empty_dict() -> None:
    assert gsc_engine.fetch_gsc_url_inspections_batch(object(), "", ["https://example.com/"]) == {}


class _FakeInspectionService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.call_count = 0

    def urlInspection(self) -> "_FakeInspectionService":  # noqa: N802 - matches googleapiclient naming
        return self

    def index(self) -> "_FakeInspectionService":
        return self

    def inspect(self, body: dict[str, object]) -> "_FakeInspectionService":
        del body
        self.call_count += 1
        return self

    def execute(self) -> dict[str, object]:
        return self._payload


def test_fetch_gsc_url_inspections_batch_populates_from_fake_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gsc_engine, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        gsc_engine,
        "_parse_inspection_to_row_fields",
        lambda payload: {"GSC Inspection Verdict": payload.get("verdict")},
    )
    service = _FakeInspectionService({"verdict": "PASS"})

    result = gsc_engine.fetch_gsc_url_inspections_batch(
        service, "sc-domain:example.com", ["https://example.com/page/"]
    )

    assert result["https://example.com/page/"] == {"GSC Inspection Verdict": "PASS"}
    assert service.call_count == 1

    # Second call for the same URL must hit the SQLite cache, not the fake service again.
    result2 = gsc_engine.fetch_gsc_url_inspections_batch(
        service, "sc-domain:example.com", ["https://example.com/page/"]
    )
    assert result2["https://example.com/page/"] == {"GSC Inspection Verdict": "PASS"}
    assert service.call_count == 1
