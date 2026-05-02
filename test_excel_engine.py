"""
Temporary local test: re-run Excel formatting (column widths, Dashboard KPIs)
without a network crawl. Reads the latest audit xlsx from output/, writes
test_dashboard_fix.xlsx.

Delete this file when you are done verifying.

Usage:
  python test_excel_engine.py
  python test_excel_engine.py path/to/SEO_AEO_Audit_....xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from reporters.sheets.tables_impl import adjust_sheet_format, apply_tab_hyperlinks

# Same trailing pass as main.py (line ~1198), plus Main (formatted early in
# main before other sheets; including it here ensures widths/links run once
# the full workbook exists).
_ADJUST_SHEET_ORDER: tuple[str, ...] = (
    "Main",
    "Dashboard",
    "Content Optimization Hub",
    "Quick Reference Guide",
    "FixPlan",
    "Glossary & Legend",
    "Technical",
    "Content",
    "Links",
    "LinksDetail",
    "Media",
    "Schema & Metadata",
    "AEO",
    "AIOSEO",
    "Security",
    "Indexability",
    "Redirects",
    "Duplicates",
    "Pattern and Template Issues",
    "PSI Performance",
    "Priority URLs",
    "IssueInventory",
    "ResolvedIssues",
    "RunMetadata",
    "DeltaFromPreviousRun",
    "CrawlGraph",
    "SitemapQA",
    "Summary",
)


def _pick_latest_audit_xlsx(search_roots: list[Path]) -> Path:
    candidates: list[Path] = []
    for root in search_roots:
        if not root.is_dir():
            continue
        hits = list(root.glob("SEO_AEO_Audit*.xlsx"))
        if not hits:
            hits = list(root.glob("*.xlsx"))
        candidates.extend(hits)
    if not candidates:
        msg = f"No .xlsx found under {search_roots!r}"
        raise FileNotFoundError(msg)
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        source = Path(sys.argv[1]).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
    else:
        source = _pick_latest_audit_xlsx([repo_root / "output", repo_root])
    print(f"Source workbook: {source}")

    frames: dict[str, pd.DataFrame] = pd.read_excel(
        source, sheet_name=None, engine="openpyxl"
    )

    # Canonical tab names in this project; support a misnamed export if present.
    main_df = frames.get("Main") or frames.get("Main_Data")
    inv_df = frames.get("IssueInventory")
    print(
        "Loaded sheets:",
        len(frames),
        "| Main:",
        "Main" in frames or "Main_Data" in frames,
        "| IssueInventory:",
        "IssueInventory" in frames,
    )
    if main_df is not None:
        print(f"  Main/Main_Data rows: {len(main_df)}")
    if inv_df is not None:
        print(f"  IssueInventory rows: {len(inv_df)}")

    dest = repo_root / "test_dashboard_fix.xlsx"
    with pd.ExcelWriter(dest, engine="openpyxl") as writer:
        for sheet_name, df in frames.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        apply_tab_hyperlinks(writer)

        for sname in _ADJUST_SHEET_ORDER:
            if sname in writer.sheets:
                print(f"  adjust_sheet_format -> {sname}")
                adjust_sheet_format(writer, sname)

    print(f"Wrote: {dest}")


if __name__ == "__main__":
    main()
