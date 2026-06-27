"""Offline integration smoke: assemble a fixture page through extraction validators (D5)."""
from __future__ import annotations

import json
from pathlib import Path

from hype_frog.crawler.data_assembler import assemble_from_html, finalize_row_state, init_rows
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.crawler import psi_engine as psi
from hype_frog.extractors.schema import extract_json_ld_blocks
from hype_frog.validators.schema_validator import validate_schemas_from_html


def test_sample_page_assemble_populates_schema_and_eeat(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "sample_page.html").read_text(encoding="utf-8")
    url = "https://example.com/news/conference-recap"
    main_dict, extra_dict = init_rows(url, None)
    main_payload = MainRowPayload.model_validate(main_dict)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)

    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url=url,
        response_headers={"Last-Modified": "Wed, 01 Jun 2025 12:00:00 GMT"},
    )
    finalize_row_state(main_payload, extra_payload)
    extra = extra_payload.values

    assert extra["Schema Present"] is True
    assert extra["Schema Valid"] is True
    assert (extra["E-E-A-T Signal Score"] or 0) >= 6
    assert extra["Has Privacy Policy Link"] is True
    assert extra["Freshness Status"] != "Unknown"


def test_sample_schema_fixture_validates() -> None:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    payload = json.loads((fixtures_dir / "sample_schema.json").read_text(encoding="utf-8"))
    valid_raw = json.dumps(payload["valid_faqpage"])
    result = validate_schemas_from_html("https://example.com/faq", [valid_raw])
    assert result.is_fully_valid is True

    invalid_raw = json.dumps(payload["invalid_faqpage_missing_main_entity"])
    invalid_result = validate_schemas_from_html("https://example.com/faq-bad", [invalid_raw])
    assert invalid_result.error_count >= 1


def test_sample_psi_response_merges_lab_and_crux(fixtures_dir: Path) -> None:
    payload = json.loads((fixtures_dir / "sample_psi_response.json").read_text(encoding="utf-8"))
    merged = psi._merge_url_results(
        "https://example.com/page",
        payload,
        payload,
    )
    assert merged["PSI Data Status"] == "PSI + CrUX Field (URL)"
    assert merged["Mobile Score"] == 72
    assert merged["CWV LCP (s)"] == 2.4


def test_extract_json_ld_blocks_from_sample_page(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "sample_page.html").read_text(encoding="utf-8")
    blocks = extract_json_ld_blocks(html)
    assert len(blocks) == 1
    assert "Article" in blocks[0]
