"""Executive summary PDF export (C2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hype_frog.reporter.pdf_exporter import export_executive_summary_pdf


def test_export_executive_summary_pdf_writes_file(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(
        workbook_path=str(workbook),
        client_domain="example.com",
        summary_rows=[
            {
                "Section": "Issue Counts",
                "Issue": "Missing Meta Description",
                "Severity": "Warning",
                "Affected URL Count": 2,
            }
        ],
        fixplan_rows=[
            {
                "Issue Type": "Missing Meta Description",
                "Severity": "Warning",
                "Affected Count": 2,
                "Effort": "S",
                "Owner": "Copy Writer",
            }
        ],
        main_rows=[{"URL": "https://example.com/a", "SEO Health Score": 72}],
        extra_rows=[{"URL": "https://example.com/a", "AEO Readiness Score": 65}],
    )
    assert pdf_path is not None
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 0
