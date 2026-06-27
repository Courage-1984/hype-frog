"""PSI enrichment assembly: lookup keys and unavailable messaging."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload
from hype_frog.pipeline.assemble import row_with_psi_gsc_harden


def test_row_with_psi_gsc_harden_uses_normalized_final_url_lookup() -> None:
    row = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/old",
            "Final URL": "https://example.com/final/",
        }
    )
    psi_map = {
        "https://example.com/final": {
            "PSI Data Status": "PSI Lab",
            "Desktop Score": 77,
            "Mobile Score": 65,
            "Mobile LCP": 2.1,
            "Mobile CLS": 0.04,
            "Mobile TTFB": 0.5,
            "CrUX Level": "None",
            "CWV LCP (s)": None,
            "CWV CLS": None,
            "CWV Data Source": "None",
            "Field vs Lab": "Lab only",
        }
    }
    hardened = row_with_psi_gsc_harden(
        row,
        url_key="https://example.com/final/",
        normalized_key="https://example.com/final",
        psi_map=psi_map,
        gsc_metrics={},
    )
    assert hardened.values["PSI Data Status"] == "PSI Lab"
    assert hardened.values["Desktop PSI Score"] == 77
    assert hardened.values["Mobile PSI Score"] == 65
    assert hardened.values["Mobile LCP (s)"] == 2.1
    assert hardened.values["CWV LCP (s)"] is None


def test_row_with_psi_gsc_harden_preserves_origin_crux_without_cwv_fallback() -> None:
    row = ExtraRowPayload.model_validate({"URL": "https://example.com/page"})
    psi_map = {
        "https://example.com/page": {
            "PSI Data Status": "PSI + CrUX Field (Origin)",
            "Desktop Score": 80,
            "Mobile Score": 55,
            "Mobile LCP": 7.3,
            "Mobile CLS": 0.12,
            "CrUX Level": "Origin",
            "CWV LCP (s)": None,
            "Origin CrUX LCP (s)": 11.852,
            "CWV Data Source": "CrUX API (Origin-level)",
            "Field vs Lab": "Lab (Origin CrUX available)",
        }
    }
    hardened = row_with_psi_gsc_harden(
        row,
        url_key="https://example.com/page",
        normalized_key="https://example.com/page",
        psi_map=psi_map,
        gsc_metrics={},
    )
    assert hardened.values["CrUX Level"] == "Origin"
    assert hardened.values["CWV LCP (s)"] is None
    assert hardened.values["Origin CrUX LCP (s)"] == 11.852
    assert hardened.values["Mobile LCP (s)"] == 7.3


def test_row_with_psi_gsc_harden_does_not_zero_when_psi_missing() -> None:
    row = ExtraRowPayload.model_validate({"URL": "https://example.com/"})
    hardened = row_with_psi_gsc_harden(
        row,
        url_key="https://example.com",
        normalized_key="https://example.com",
        psi_map={},
        gsc_metrics={},
    )
    assert hardened.values["PSI Data Status"] == "Not measured (PSI disabled)"
    assert hardened.values["Desktop PSI Score"] is None
    assert hardened.values["Mobile PSI Score"] is None


def test_row_with_psi_gsc_harden_preserves_unavailable_status() -> None:
    row = ExtraRowPayload.model_validate({"URL": "https://example.com/fail"})
    psi_map = {
        "https://example.com/fail": {
            "PSI Data Status": "Unavailable (mobile: HTTP 400; desktop: HTTP 400)",
            "Desktop Score": None,
            "Mobile Score": None,
        }
    }
    hardened = row_with_psi_gsc_harden(
        row,
        url_key="https://example.com/fail",
        normalized_key="https://example.com/fail",
        psi_map=psi_map,
        gsc_metrics={},
    )
    assert "Unavailable" in str(hardened.values["PSI Data Status"])
    assert hardened.values["Desktop PSI Score"] is None
    assert hardened.values["Mobile PSI Score"] is None
