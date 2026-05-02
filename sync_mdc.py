#!/usr/bin/env python3
"""
Rewrite `.cursor/rules/*.mdc` globs and obvious path literals for the `src/hype_frog/` layout.

Dry-run by default; pass --write to persist changes.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def _transform_body(text: str) -> str:
    out = text

    # globs: reporters -> src package reporter
    out = out.replace("reporters/**/*.py", "src/hype_frog/reporter/**/*.py")
    out = out.replace("reporters/", "src/hype_frog/reporter/")

    # brace globs from crawler_agent style
    out = out.replace(
        "{crawler,extractors,pipeline,core}/**/*.py",
        "{src/hype_frog/crawler,src/hype_frog/extractors,src/hype_frog/pipeline,src/hype_frog/core}/**/*.py",
    )

    out = out.replace("crawler/**/*.py", "src/hype_frog/crawler/**/*.py")
    out = out.replace("extractors/**/*.py", "src/hype_frog/extractors/**/*.py")
    out = out.replace("pipeline/**/*.py", "src/hype_frog/pipeline/**/*.py")
    out = out.replace("core/**/*.py", "src/hype_frog/core/**/*.py")

    # prose path hints
    out = out.replace("`pipeline.export`", "`src/hype_frog/pipeline/export.py`")
    out = out.replace("`main.py`", "`src/hype_frog/entry_main.py`")

    # de-duplicate accidental double prefixes if run twice
    out = re.sub(
        r"src/hype_frog/(src/hype_frog/)+",
        "src/hype_frog/",
        out,
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes in place (default is dry-run).",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root (default: parent of this script).",
    )
    args = parser.parse_args()
    repo = (args.repo or Path(__file__).resolve().parent).resolve()
    rules = repo / ".cursor" / "rules"
    if not rules.is_dir():
        print(f"No rules directory: {rules}")
        return
    for path in sorted(rules.glob("*.mdc")):
        raw = path.read_text(encoding="utf-8")
        new = _transform_body(raw)
        if new == raw:
            print(f"OK (unchanged): {path.name}")
            continue
        print(f"UPDATE: {path.name}")
        if args.write:
            path.write_text(new, encoding="utf-8", newline="\n")
        else:
            print("  (dry-run; pass --write to apply)")
    if not args.write:
        print("\nDry-run complete. Re-run with --write to apply edits.")


if __name__ == "__main__":
    main()
