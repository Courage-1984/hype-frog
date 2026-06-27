"""PSI batch merge, status messaging, and map indexing."""

from __future__ import annotations

from hype_frog.crawler import psi_engine as psi


def _sample_payload(*, perf: int = 90, lcp_ms: float = 2500.0, cls: float = 0.05) -> dict:
    return {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": perf / 100.0},
                "accessibility": {"score": 0.85},
                "best-practices": {"score": 0.78},
                "seo": {"score": 0.92},
            },
            "audits": {
                "largest-contentful-paint": {"numericValue": lcp_ms, "score": 0.6},
                "cumulative-layout-shift": {"numericValue": cls, "score": 0.9},
                "interaction-to-next-paint": {"numericValue": 120.0, "score": 0.8},
                "total-blocking-time": {"numericValue": 180.0, "score": 0.7},
                "first-contentful-paint": {"numericValue": 1800.0, "score": 0.75},
                "speed-index": {"numericValue": 3200.0, "score": 0.65},
                "interactive": {"numericValue": 4100.0, "score": 0.6},
                "server-response-time": {"numericValue": 400.0, "score": 0.8},
                "total-byte-weight": {"numericValue": 512000.0, "score": 0.5},
                "dom-size": {"numericValue": 842.0, "score": 0.7},
                "bootup-time": {"numericValue": 1250.0, "score": 0.6},
                "network-requests": {
                    "details": {"items": [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}]}
                },
                "uses-text-compression": {"score": 1.0},
                "uses-long-cache-ttl": {"score": 0.5},
                "render-blocking-resources": {"score": 0.0},
                "uses-webp-images": {"score": 0.0},
                "modern-image-formats": {"score": 1.0},
            },
        },
        "loadingExperience": {
            "id": "https://example.com/page",
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2200, "category": "FAST"},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 8, "category": "GOOD"},
            },
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
    assert merged["CrUX Level"] == "None"
    assert merged["Mobile Score"] == 90
    assert merged["Desktop Score"] == 90
    assert merged["CWV LCP (s)"] is None
    assert merged["Mobile LCP"] == 2.5
    assert merged["Field vs Lab"] == "Lab only"
    assert merged["CWV Data Source"] == "None"


def test_merge_url_results_psi_plus_url_crux() -> None:
    merged = psi._merge_url_results(
        "https://example.com/page",
        _sample_payload(),
        _sample_payload(perf=88),
    )
    assert merged["PSI Data Status"] == "PSI + CrUX Field (URL)"
    assert merged["CrUX Level"] == "URL"
    assert merged["Field vs Lab"] == "Field (URL-level CrUX)"
    assert merged["CWV Data Source"] == "CrUX API (URL-level)"
    assert merged["CWV LCP (s)"] == 2.2
    assert merged["CrUX LCP Category"] == "FAST"
    assert merged["Origin CrUX LCP (s)"] is None
    assert merged["Lighthouse Performance (Mobile)"] == 90
    assert merged["Lighthouse Accessibility (Mobile)"] == 85
    assert merged["Lighthouse Best Practices (Mobile)"] == 78
    assert merged["Lab LCP (Mobile) (s)"] == 2.5
    assert merged["Lab TBT (Mobile) (ms)"] == 180.0
    assert merged["Page Size (KB)"] == 500.0
    assert merged["DOM Size (nodes)"] == 842
    assert merged["Has Render Blocking Resources"] is True
    assert merged["Uses Modern Image Formats"] is True
    assert merged["Mobile Score"] == 90
    assert merged["Mobile LCP"] == 2.5


def test_build_endpoint_requests_all_lighthouse_categories() -> None:
    endpoint = psi._build_endpoint("https://example.com", "mobile", "test-key")
    assert "category=performance" in endpoint
    assert "category=accessibility" in endpoint
    assert "category=best-practices" in endpoint
    assert "category=seo" in endpoint


def test_extract_lighthouse_data_desktop_skips_mobile_only_columns() -> None:
    payload = _sample_payload()["lighthouseResult"]
    desktop = psi._extract_lighthouse_data(payload, prefix="desktop")
    assert desktop["Lighthouse Performance (Desktop)"] == 90
    assert desktop["Lab LCP (Desktop) (s)"] == 2.5
    assert "Page Size (KB)" not in desktop


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
    assert merged["CrUX Level"] == "Origin"
    assert merged["Field vs Lab"] == "Field (Origin)"
    assert merged["CWV Data Source"] == "CrUX API (Origin-level)"
    assert merged["CWV LCP (s)"] is None
    assert merged["Origin CrUX LCP (s)"] == 5.1


def test_detect_crux_level_origin_fallback_flag() -> None:
    payload = {
        "loadingExperience": {
            "origin_fallback": True,
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 11852}},
        },
        "originLoadingExperience": {
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 11852}},
        },
    }
    metrics, level = psi._detect_crux_level(
        payload, "https://africanmarketingconfederation.org/about-us"
    )
    assert level == "Origin"
    assert metrics is not None
    merged = psi._merge_url_results(
        "https://africanmarketingconfederation.org/about-us",
        {**payload, "lighthouseResult": _sample_payload()["lighthouseResult"]},
        {},
    )
    assert merged["CrUX Level"] == "Origin"
    assert merged["CWV LCP (s)"] is None
    assert merged["Origin CrUX LCP (s)"] == 11.852


def test_detect_crux_level_origin_id_path_heuristic() -> None:
    payload = {
        "loadingExperience": {
            "id": "https://example.com/",
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 4000}},
        }
    }
    metrics, level = psi._detect_crux_level(payload, "https://example.com/deep/page")
    assert level == "Origin"
    assert metrics is not None


def test_field_experience_metrics_tracks_crux_data_level() -> None:
    url_payload = {
        "loadingExperience": {
            "id": "https://example.com/page",
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2000}},
        }
    }
    origin_payload = {
        "originLoadingExperience": {
            "metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 3000}},
        }
    }
    url_metrics = psi._field_experience_metrics(
        url_payload, "https://example.com/page"
    )
    origin_metrics = psi._field_experience_metrics(origin_payload)
    assert url_metrics is not None
    assert url_metrics["crux_data_level"] == "url"
    assert origin_metrics is not None
    assert origin_metrics["crux_data_level"] == "origin"


def test_merge_url_results_partial_mobile_failure() -> None:
    desktop = {
        "lighthouseResult": _sample_payload(perf=88)["lighthouseResult"],
    }
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
    assert merged["CrUX Level"] == "None"
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
