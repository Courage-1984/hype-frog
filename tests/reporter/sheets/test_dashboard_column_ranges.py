"""Dashboard Excel helpers stay header-resolved (no brittle fixed column letters)."""

from hype_frog.reporter.sheets import dashboard as d


def test_technical_diagnostics_data_column_uses_offset_match() -> None:
    s = d._technical_diagnostics_data_column("Status Code")
    assert "OFFSET(" in s and "MATCH(" in s
    assert "Status Code" in s
    assert d._TD_SHEET in s


def test_main_sheet_data_column_uses_offset_match() -> None:
    s = d._main_sheet_data_column("Has Valid JSON-LD")
    assert "OFFSET('Main'!$A$1" in s
    assert "Has Valid JSON-LD" in s


def test_technical_url_denominator_wraps_counta() -> None:
    s = d._technical_url_row_denominator()
    assert s.startswith("MAX(1,COUNTA(")
    assert "URL" in s
