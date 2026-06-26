"""PSI batch merge, status messaging, and map indexing."""

from __future__ import annotations

from hype_frog.crawler import psi_engine as psi


def _sample_payload(*, perf: int = 90, lcp_ms: float = 2500.0, cls: float = 0.05) -> dict:
    return {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": perf / 100.0},
                "seo": {"score": 0.92},
            },
            "audits": {
                "largest-contentful-paint": {"numericValue": lcp_ms},
                "cumulative-layout-shift": {"numericValue": cls},
                "interaction-to-next-paint": {"numericValue": 120.0},
                "server-response-time": {"numericValue": 400.0},
            },
        },
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2200},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 8},
            }
        },
    }


def test_merge_url_results_lab_only_when_no_crux() -> None:
    payload = {
        "lighthouseResult": _sample_payload()["lighthouseResult"],
    }
    merged = psi._merge_url_results(
        "https://example.com/page",
        payload,
        payload,
    )
    assert merged["PSI Data Status"] == "PSI Lab"
    assert merged["Mobile Score"] == 90
    assert merged["Desktop Score"] == 90
    assert merged["CWV LCP (s)"] == 2.5
    assert merged["Field vs Lab"] == "Lab"
    assert merged["CWV Data Source"] == "PSI API (Lighthouse)"


def test_merge_url_results_psi_plus_url_crux() -> None:
    merged = psi._merge_url_results(
        "https://example.com/page",
        _sample_payload(),
        _sample_payload(perf=88),
    )
    assert merged["PSI Data Status"] == "PSI + CrUX Field (URL)"
    assert merged["Field vs Lab"] == "Field"
    assert merged["CWV Data Source"] == "PSI API (CrUX)"
    assert merged["CWV LCP (s)"] == 2.2


def test_merge_url_results_origin_crux_only() -> None:
    payload = {
        "originLoadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 5100},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 15},
            }
        }
    }
    merged = psi._merge_url_results(
        "https://example.com/rare",
        payload,
        payload,
    )
    assert merged["PSI Data Status"] == "CrUX Field (Origin)"
    assert merged["Field vs Lab"] == "Field (Origin)"
    assert "Origin" in str(merged["CWV Data Source"])
    assert merged["CWV LCP (s)"] == 5.1


def test_field_experience_metrics_tracks_crux_data_level() -> None:
    url_payload = {
        "loadingExperience": {
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2000}}
        }
    }
    origin_payload = {
        "originLoadingExperience": {
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 3000}}
        }
    }
    url_metrics = psi._field_experience_metrics(url_payload)
    origin_metrics = psi._field_experience_metrics(origin_payload)
    assert url_metrics is not None
    assert url_metrics["crux_data_level"] == "url"
    assert origin_metrics is not None
    assert origin_metrics["crux_data_level"] == "origin"


def test_merge_url_results_partial_mobile_failure() -> None:
    desktop = _sample_payload(perf=88)
    merged = psi._merge_url_results(
        "https://example.com/",
        {},
        desktop,
        mobile_error="HTTP 400",
        desktop_error=None,
    )
    assert merged["Mobile Score"] is None
    assert merged["Desktop Score"] == 88
    assert merged["PSI Data Status"] == "PSI Lab"
    assert merged["CWV LCP (s)"] is None


def test_merge_url_results_unavailable_both_strategies() -> None:
    merged = psi._merge_url_results(
        "https://example.com/broken",
        {},
        {},
        mobile_error="FAILED_DOCUMENT_REQUEST",
        desktop_error="HTTP 400",
    )
    assert str(merged["PSI Data Status"]).startswith("Unavailable")
    assert merged["Mobile Score"] is None
    assert merged["Desktop Score"] is None


def test_psi_index_key_matches_normalized_url() -> None:
    assert psi.psi_index_key("https://Example.com/page/") == psi.psi_index_key(
        "https://example.com/page"
    )


def test_store_psi_result_indexes_normalized_key() -> None:
    results: dict[str, dict] = {}
    merged = {"URL": "https://example.com/x", "PSI Data Status": "PSI Lab"}
    psi._store_psi_result(results, "https://example.com/x/", merged)
    assert "https://example.com/x/" in results
    norm = psi.psi_index_key("https://example.com/x")
    assert results[norm] is merged


def test_retryable_psi_error_detects_quota_and_load_failures() -> None:
    assert psi._is_retryable_psi_error(400, "Quota exceeded for quota metric")
    assert psi._is_retryable_psi_error(400, "Lighthouse returned error: FAILED_DOCUMENT_REQUEST")
    assert not psi._is_retryable_psi_error(400, "API key not valid. Please pass a valid API key.")


def test_resolve_psi_data_status_complete_with_field() -> None:
    status = psi._resolve_psi_data_status(
        mobile_ok=True,
        desktop_ok=True,
        has_field=True,
        mobile_error=None,
        desktop_error=None,
    )
    assert status == "Complete (Lab + Field)"
