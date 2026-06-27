"""Tests for extractors/freshness.py — date extraction and freshness classification."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from hype_frog.extractors.freshness import extract_freshness_signals


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _days_ago(n: int) -> str:
    d = datetime.now(tz=timezone.utc) - timedelta(days=n)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestHttpLastModifiedHeader:
    def test_sets_http_last_modified_from_header(self) -> None:
        extra: dict = {}
        extract_freshness_signals(
            {"Last-Modified": "Wed, 21 Oct 2023 07:28:00 GMT"},
            _soup(""),
            extra,
        )
        assert extra["HTTP Last-Modified"] == "Wed, 21 Oct 2023 07:28:00 GMT"

    def test_fallback_header_key_lowercase(self) -> None:
        extra: dict = {}
        extract_freshness_signals(
            {"last-modified": "Wed, 21 Oct 2023 07:28:00 GMT"},
            _soup(""),
            extra,
        )
        assert extra["HTTP Last-Modified"] == "Wed, 21 Oct 2023 07:28:00 GMT"

    def test_no_header_sets_none(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["HTTP Last-Modified"] is None


class TestArticleMetaTags:
    def test_published_time_from_article_meta(self) -> None:
        html = '<meta property="article:published_time" content="2024-03-15T10:00:00Z">'
        extra: dict = {}
        extract_freshness_signals({}, _soup(html), extra)
        assert extra["Published Date"] == "2024-03-15T10:00:00Z"

    def test_modified_time_from_article_meta(self) -> None:
        html = '<meta property="article:modified_time" content="2024-04-01T12:00:00Z">'
        extra: dict = {}
        extract_freshness_signals({}, _soup(html), extra)
        assert extra["Last Modified Date"] == "2024-04-01T12:00:00Z"

    def test_modified_falls_back_to_header_when_meta_absent(self) -> None:
        extra: dict = {}
        extract_freshness_signals(
            {"Last-Modified": "Tue, 01 Jan 2019 00:00:00 GMT"},
            _soup(""),
            extra,
        )
        assert extra["Last Modified Date"] == "Tue, 01 Jan 2019 00:00:00 GMT"


class TestSchemaFallback:
    def test_published_date_falls_back_to_schema_published(self) -> None:
        extra: dict = {"Schema Published Date": "2023-06-01"}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["Published Date"] == "2023-06-01"

    def test_last_modified_falls_back_to_schema_modified(self) -> None:
        extra: dict = {"Schema Modified Date": "2023-09-01"}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["Last Modified Date"] == "2023-09-01"

    def test_modified_date_mirrored_to_modified_date_key(self) -> None:
        html = '<meta property="article:modified_time" content="2024-05-01T00:00:00Z">'
        extra: dict = {}
        extract_freshness_signals({}, _soup(html), extra)
        assert extra.get("Modified Date") == "2024-05-01T00:00:00Z"


def _soup_with_modified(date_str: str) -> BeautifulSoup:
    """Return soup with article:modified_time meta so extract_freshness_signals picks it up."""
    html = f'<meta property="article:modified_time" content="{date_str}">'
    return _soup(html)


class TestFreshnessClassification:
    def test_fresh_within_90_days(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup_with_modified(_days_ago(30)), extra)
        assert extra["Freshness Status"] == "Fresh (< 3 months)"

    def test_recent_3_to_12_months(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup_with_modified(_days_ago(120)), extra)
        assert extra["Freshness Status"] == "Recent (3-12 months)"

    def test_ageing_1_to_2_years(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup_with_modified(_days_ago(500)), extra)
        assert extra["Freshness Status"] == "Ageing (1-2 years)"

    def test_stale_over_2_years(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup_with_modified(_days_ago(800)), extra)
        assert extra["Freshness Status"] == "Stale (> 2 years)"

    def test_no_date_yields_unknown(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["Freshness Status"] == "Unknown"
        assert extra["Content Age (days)"] is None

    def test_unparseable_date_in_schema_yields_unknown(self) -> None:
        extra: dict = {"Schema Modified Date": "not-a-date"}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["Freshness Status"] == "Unknown"
        assert extra["Content Age (days)"] is None

    def test_content_age_days_is_integer(self) -> None:
        extra: dict = {}
        extract_freshness_signals({}, _soup_with_modified(_days_ago(45)), extra)
        assert isinstance(extra["Content Age (days)"], int)
        assert extra["Content Age (days)"] >= 40

    def test_schema_fallback_drives_freshness(self) -> None:
        extra: dict = {"Schema Modified Date": _days_ago(800)}
        extract_freshness_signals({}, _soup(""), extra)
        assert extra["Freshness Status"] == "Stale (> 2 years)"
