"""Tests for schema.org JSON-LD validation."""
from __future__ import annotations

import pytest

from hype_frog.validators.schema_validator import validate_schemas_from_html


def test_no_schema_returns_no_schema_summary() -> None:
    result = validate_schemas_from_html("https://example.com/", [])
    assert result.has_any_schema is False
    assert result.summary == "No schema"


def test_faqpage_missing_main_entity_counts_error() -> None:
    blocks = [
        '{"@context":"https://schema.org","@type":"FAQPage","name":"FAQ"}'
    ]
    result = validate_schemas_from_html("https://example.com/faq", blocks)
    assert result.has_any_schema is True
    assert result.error_count >= 1
    assert "FAQPage" in result.types_with_errors


@pytest.mark.parametrize(
    ("schema_type", "block", "expect_valid", "expect_error_type"),
    [
        (
            "Article",
            '{"@type":"Article","headline":"Guide","author":"Jane Doe","datePublished":"2026-01-01"}',
            True,
            None,
        ),
        (
            "Article",
            '{"@type":"Article","headline":"Guide","datePublished":"2026-01-01"}',
            False,
            "Article",
        ),
        (
            "Event",
            '{"@type":"Event","name":"Summit","startDate":"2026-06-01","location":"London"}',
            True,
            None,
        ),
        (
            "BreadcrumbList",
            '{"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home"}]}',
            True,
            None,
        ),
        (
            "BreadcrumbList",
            '{"@type":"BreadcrumbList","name":"Trail"}',
            False,
            "BreadcrumbList",
        ),
        (
            "Product",
            '{"@type":"Product","name":"Widget","offers":{"@type":"Offer","price":"9.99","priceCurrency":"GBP"}}',
            True,
            None,
        ),
        (
            "Product",
            '{"@type":"Product","name":"Widget"}',
            False,
            "Product",
        ),
    ],
)
def test_schema_type_validation(
    schema_type: str,
    block: str,
    expect_valid: bool,
    expect_error_type: str | None,
) -> None:
    result = validate_schemas_from_html("https://example.com/", [block])
    assert result.has_any_schema is True
    assert schema_type in result.types_found
    if expect_valid:
        assert schema_type in result.types_valid
        assert schema_type not in result.types_with_errors
    else:
        assert expect_error_type in result.types_with_errors
        assert result.error_count >= 1


def test_graph_array_validates_each_node() -> None:
    block = (
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebPage","name":"Home"},'
        '{"@type":"Organization","name":"Acme","url":"https://example.com"}'
        "]}"
    )
    result = validate_schemas_from_html("https://example.com/", [block])
    assert result.has_any_schema is True
    assert "WebPage" in result.types_valid
    assert "Organization" in result.types_valid
    assert result.error_count == 0


def test_malformed_json_records_parse_error() -> None:
    result = validate_schemas_from_html("https://example.com/", ["{not valid json"])
    assert result.has_any_schema is True
    assert result.parse_errors
    assert result.error_count >= 1
    assert not result.is_fully_valid
