"""Phase 1 guards: canonical RAG palette + authoritative CF kill switch."""

from __future__ import annotations

import openpyxl

from hype_frog.reporter import engine_formatting
from hype_frog.reporter.sheets import config, dashboard_config


def _rule_count(worksheet: openpyxl.worksheet.worksheet.Worksheet) -> int:
    return sum(len(rules) for rules in worksheet.conditional_formatting._cf_rules.values())


def test_dashboard_rag_aliases_resolve_to_canonical_palette() -> None:
    """dashboard_config RAG names must equal the single source of truth (P1.2)."""
    assert dashboard_config.GOOD_COLOR == config.RAG_GREEN
    assert dashboard_config.WARN_COLOR == config.RAG_AMBER
    assert dashboard_config.ALERT_COLOR == config.RAG_RED
    assert dashboard_config.SOFT_ALERT_COLOR == config.RAG_RED_SOFT
    assert dashboard_config.SOFT_WARN_COLOR == config.RAG_AMBER_SOFT


def _sheet_with_scores() -> openpyxl.worksheet.worksheet.Worksheet:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["URL", "SEO Health Score", "Severity Badge", "Status Code"])
    ws.append(["https://e.example/", 80, "Warning", 200])
    ws.append(["https://e.example/b", 30, "Critical", 404])
    return ws


def test_global_cf_disabled_adds_no_rules(monkeypatch) -> None:
    """HF_DISABLE_CONDITIONAL_FORMATTING must be honoured inside the global pass (P1.1)."""
    monkeypatch.setattr(engine_formatting, "DISABLE_CONDITIONAL_FORMATTING", True)
    ws = _sheet_with_scores()
    engine_formatting.apply_global_conditional_formatting(ws)
    assert _rule_count(ws) == 0


def test_global_cf_enabled_adds_rules(monkeypatch) -> None:
    monkeypatch.setattr(engine_formatting, "DISABLE_CONDITIONAL_FORMATTING", False)
    ws = _sheet_with_scores()
    engine_formatting.apply_global_conditional_formatting(ws)
    assert _rule_count(ws) > 0


def test_global_cf_skip_headers_suppresses_owned_columns(monkeypatch) -> None:
    """skip_headers lets Main's heatmap pass own a column without double-CF (P1.3)."""
    monkeypatch.setattr(engine_formatting, "DISABLE_CONDITIONAL_FORMATTING", False)
    full = _sheet_with_scores()
    engine_formatting.apply_global_conditional_formatting(full)
    skipped = _sheet_with_scores()
    engine_formatting.apply_global_conditional_formatting(
        skipped, skip_headers=frozenset({"SEO Health Score", "Severity Badge", "Status Code"})
    )
    assert _rule_count(skipped) < _rule_count(full)
