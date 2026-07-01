"""CLI shim — delegates to ``hype_frog.reporter.workbook_audit``."""

from __future__ import annotations

import sys
from pathlib import Path

from hype_frog.core.path_bootstrap import bootstrap_src_path, repo_root

bootstrap_src_path(anchor=Path(__file__))
ROOT = repo_root()

from hype_frog.reporter.workbook_audit import audit_workbook  # noqa: E402


def _latest_audit_xlsx() -> Path:
    latest_dir = ROOT / "reports" / "latest"
    candidates = sorted(
        latest_dir.glob("SEO_AEO_Audit*.xlsx"), key=lambda p: p.stat().st_mtime
    )
    if not candidates:
        raise FileNotFoundError(f"No SEO_AEO_Audit*.xlsx under {latest_dir}")
    return candidates[-1]


def main() -> int:
    path = _latest_audit_xlsx()
    print(f"AUDIT_FILE={path}")
    errors = audit_workbook(path)
    if errors:
        print("AUDIT_STATUS=FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("AUDIT_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
