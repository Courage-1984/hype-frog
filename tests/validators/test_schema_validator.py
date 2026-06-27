"""Tests for schema.org JSON-LD validation."""
from __future__ import annotations

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
