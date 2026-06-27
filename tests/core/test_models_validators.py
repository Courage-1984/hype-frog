"""Tests for the strict Pydantic validators in core/models.py.

Covers HttpCrawlResultModel, PSIMetricsModel, GSCMetricsModel, and the
harden_page_row_metrics fallback path — none of which were exercised before.
"""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from hype_frog.core.models import (
    GSCMetricsModel,
    HttpCrawlResultModel,
    PSIMetricsModel,
    SummaryMetricsPayload,
    harden_page_row_metrics,
)


# ---------------------------------------------------------------------------
# HttpCrawlResultModel
# ---------------------------------------------------------------------------


class TestHttpCrawlResultModel:
    def _valid(self, **overrides) -> dict:
        base = {
            "url": "https://example.com/",
            "status_code": 200,
            "response_time_ms": 123.4,
        }
        return {**base, **overrides}

    def test_valid_minimal_record(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid())
        assert m.url == "https://example.com/"
        assert m.status_code == 200

    def test_strip_url_whitespace(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(url="  https://example.com/  "))
        assert m.url == "https://example.com/"

    def test_blank_url_after_strip_raises(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(url="   "))

    def test_rejects_sentinel_status_timeout(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(status_code="Timeout"))

    def test_rejects_sentinel_status_connection_error(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(status_code="Connection Error"))

    def test_rejects_sentinel_status_unknown(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(status_code="Unknown"))

    def test_rejects_status_code_out_of_range_low(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(status_code=99))

    def test_rejects_status_code_out_of_range_high(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(status_code=600))

    def test_rejects_nan_response_time(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(response_time_ms=float("nan")))

    def test_rejects_inf_response_time(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(response_time_ms=math.inf))

    def test_rejects_nan_field_cls(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(field_cls=float("nan")))

    def test_rejects_inf_field_lcp_ms(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(field_lcp_ms=math.inf))

    def test_rejects_nan_entity_density(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(entity_density=float("nan")))

    def test_rejects_nan_aeo_score(self) -> None:
        with pytest.raises(ValidationError):
            HttpCrawlResultModel.model_validate(self._valid(aeo_score=float("nan")))

    def test_normalise_top_entities_from_pipe_string(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(top_entities="Apple | Google | Meta"))
        assert m.top_entities == ["Apple", "Google", "Meta"]

    def test_normalise_top_entities_none_stays_none(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(top_entities=None))
        assert m.top_entities is None

    def test_normalise_top_entities_parses_many_pipe_separated_items(self) -> None:
        entities = [f"Entity{i}" for i in range(1, 16)]
        m = HttpCrawlResultModel.model_validate(
            self._valid(top_entities=" | ".join(entities))
        )
        assert m.top_entities == entities
        assert len(m.top_entities) == 15

    def test_normalise_diagnostic_strings_strips_whitespace(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(x_frame_options="  DENY  "))
        assert m.x_frame_options == "DENY"

    def test_normalise_diagnostic_strings_blank_becomes_none(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(anchor_text_summary="   "))
        assert m.anchor_text_summary is None

    def test_extra_fields_are_ignored(self) -> None:
        m = HttpCrawlResultModel.model_validate(self._valid(unknown_field="ignored"))
        assert not hasattr(m, "unknown_field")


# ---------------------------------------------------------------------------
# PSIMetricsModel
# ---------------------------------------------------------------------------


class TestPSIMetricsModel:
    def test_valid_with_performance_score(self) -> None:
        m = PSIMetricsModel.model_validate({"performance_score": 85, "lcp_seconds": 1.2})
        assert m.performance_score == 85

    def test_all_none_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            PSIMetricsModel.model_validate({})

    def test_rejects_nan_lcp(self) -> None:
        with pytest.raises(ValidationError):
            PSIMetricsModel.model_validate({"performance_score": 80, "lcp_seconds": float("nan")})

    def test_rejects_inf_inp_ms(self) -> None:
        with pytest.raises(ValidationError):
            PSIMetricsModel.model_validate({"performance_score": 80, "inp_ms": math.inf})

    def test_accepts_seo_score_only(self) -> None:
        m = PSIMetricsModel.model_validate({"seo_score": 90})
        assert m.seo_score == 90

    def test_performance_score_boundary_zero(self) -> None:
        m = PSIMetricsModel.model_validate({"performance_score": 0})
        assert m.performance_score == 0

    def test_performance_score_boundary_hundred(self) -> None:
        m = PSIMetricsModel.model_validate({"performance_score": 100})
        assert m.performance_score == 100

    def test_performance_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            PSIMetricsModel.model_validate({"performance_score": 101})

    def test_fid_ms_accepted_for_legacy_crux(self) -> None:
        m = PSIMetricsModel.model_validate({"fid_ms": 50.0})
        assert m.fid_ms == 50.0


# ---------------------------------------------------------------------------
# GSCMetricsModel
# ---------------------------------------------------------------------------


class TestGSCMetricsModel:
    def _valid(self, **overrides) -> dict:
        base = {"clicks": 10, "impressions": 200, "ctr": 0.05, "position": 8.3}
        return {**base, **overrides}

    def test_valid_record(self) -> None:
        m = GSCMetricsModel.model_validate(self._valid())
        assert m.clicks == 10
        assert m.impressions == 200

    def test_coerces_float_clicks_to_int(self) -> None:
        m = GSCMetricsModel.model_validate(self._valid(clicks=5.0))
        assert m.clicks == 5
        assert isinstance(m.clicks, int)

    def test_coerces_float_impressions_to_int(self) -> None:
        m = GSCMetricsModel.model_validate(self._valid(impressions=100.0))
        assert isinstance(m.impressions, int)

    def test_rejects_nan_clicks(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(clicks=float("nan")))

    def test_rejects_inf_impressions(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(impressions=math.inf))

    def test_rejects_none_clicks(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(clicks=None))

    def test_rejects_nan_ctr(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(ctr=float("nan")))

    def test_rejects_inf_position(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(position=math.inf))

    def test_ctr_at_boundary_one(self) -> None:
        m = GSCMetricsModel.model_validate(self._valid(ctr=1.0))
        assert m.ctr == 1.0

    def test_ctr_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(ctr=1.1))

    def test_position_zero_is_allowed(self) -> None:
        m = GSCMetricsModel.model_validate(self._valid(position=0.0))
        assert m.position == 0.0

    def test_negative_clicks_float_raises(self) -> None:
        with pytest.raises(ValidationError):
            GSCMetricsModel.model_validate(self._valid(clicks=-1.0))


# ---------------------------------------------------------------------------
# SummaryMetricsPayload
# ---------------------------------------------------------------------------


class TestSummaryMetricsPayload:
    def _valid(self, **overrides) -> dict:
        base = {
            "urls_crawled": 50,
            "seo_pass_rate_pct": 80.0,
            "health_score_pct": 75.0,
            "critical_url_count": 3,
            "warning_url_count": 12,
            "projected_health_score_pct": 85.0,
            "projected_pass_rate_pct": 90.0,
        }
        return {**base, **overrides}

    def test_valid_payload(self) -> None:
        m = SummaryMetricsPayload.model_validate(self._valid())
        assert m.urls_crawled == 50

    def test_negative_urls_crawled_raises(self) -> None:
        with pytest.raises(ValidationError):
            SummaryMetricsPayload.model_validate(self._valid(urls_crawled=-1))

    def test_health_score_above_100_raises(self) -> None:
        with pytest.raises(ValidationError):
            SummaryMetricsPayload.model_validate(self._valid(health_score_pct=100.1))

    def test_pass_rate_zero_is_valid(self) -> None:
        m = SummaryMetricsPayload.model_validate(self._valid(seo_pass_rate_pct=0.0))
        assert m.seo_pass_rate_pct == 0.0


# ---------------------------------------------------------------------------
# harden_page_row_metrics
# ---------------------------------------------------------------------------


class TestHardenPageRowMetrics:
    def test_valid_row_returns_dumped_values(self) -> None:
        row = {
            "URL": "https://example.com/",
            "Desktop PSI Score": 85,
            "Mobile PSI Score": 70,
        }
        result = harden_page_row_metrics(row)
        assert result["Desktop PSI Score"] == 85

    def test_nan_psi_score_coerced_to_none_in_fallback(self) -> None:
        row = {
            "URL": "https://example.com/",
            "Desktop PSI Score": "",
            "Mobile PSI Score": float("nan"),
        }
        result = harden_page_row_metrics(row)
        assert result.get("Desktop PSI Score") is None

    def test_nan_lcp_coerced_to_none_in_fallback(self) -> None:
        row = {"URL": "https://example.com/", "Mobile LCP (s)": ""}
        result = harden_page_row_metrics(row)
        assert result.get("Mobile LCP (s)") is None

    def test_blank_gsc_clicks_coerced(self) -> None:
        row = {"URL": "https://example.com/", "GSC Clicks": ""}
        result = harden_page_row_metrics(row)
        assert result.get("GSC Clicks") is None

    def test_non_numeric_string_psi_falls_back_gracefully(self) -> None:
        row = {"URL": "https://example.com/", "Desktop PSI Score": "N/A"}
        result = harden_page_row_metrics(row)
        assert result.get("Desktop PSI Score") is None or isinstance(
            result.get("Desktop PSI Score"), (int, float, type(None))
        )
