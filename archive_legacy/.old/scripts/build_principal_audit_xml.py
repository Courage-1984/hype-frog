"""Emit principal_staff_audit_bundle.xml at repo root (verbatim file contents in XML)."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FILES = [
    REPO / "src/hype_frog/crawler/client.py",
    REPO / "src/hype_frog/crawler/fetcher.py",
    REPO / "src/hype_frog/crawler/engine.py",
    REPO / "src/hype_frog/pipeline/export.py",
    REPO / "src/hype_frog/pipeline/enrich.py",
    REPO / "src/hype_frog/pipeline/assemble.py",
    REPO / "src/hype_frog/pipeline/action_required.py",
    REPO / "src/hype_frog/entry_main.py",
    REPO / "src/hype_frog/reporter/excel_engine.py",
    REPO / "src/hype_frog/core/logger.py",
]


def main() -> None:
    out = REPO / "principal_staff_audit_bundle.xml"
    chunks: list[str] = []
    for path in FILES:
        rel = path.relative_to(REPO).as_posix()
        text = path.read_text(encoding="utf-8")
        chunks.append(f'<file name="{rel}">\n{text}\n</file>')
    out.write_text("\n".join(chunks), encoding="utf-8")
    print(out, out.stat().st_size)


if __name__ == "__main__":
    main()
