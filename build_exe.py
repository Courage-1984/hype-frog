#!/usr/bin/env python
"""
Build the hype-frog standalone Windows executable.

Prerequisites (run once):
    uv sync --extra dev --extra semantic --extra render

Then build:
    uv run python build_exe.py

Output: dist/hype-frog.exe
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = ROOT / "hype_frog.spec"
DIST = ROOT / "dist" / "hype-frog.exe"


def main() -> None:
    if not SPEC.exists():
        print(f"ERROR: spec file not found: {SPEC}")
        raise SystemExit(1)

    print("=" * 60)
    print("Building hype-frog.exe with PyInstaller")
    print(f"  Spec : {SPEC}")
    print(f"  Output: {DIST}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", str(SPEC)],
        cwd=ROOT,
    )

    if result.returncode != 0:
        print("\nBuild FAILED. See output above for details.")
        raise SystemExit(1)

    if not DIST.exists():
        print(f"\nBuild appeared to succeed but {DIST} was not found.")
        raise SystemExit(1)

    size_mb = DIST.stat().st_size / 1_048_576
    print(f"\n{'=' * 60}")
    print(f"Build complete:  {DIST}")
    print(f"Size:            {size_mb:.1f} MB")
    print("=" * 60)
    print()
    print("Quick smoke-test (from repo root):")
    print(f"  copy .env {DIST.parent}\\")
    print(f"  copy secrets\\client_secrets.json {DIST.parent}\\")
    print(f"  copy secrets\\token.json {DIST.parent}\\")
    print(f"  {DIST} --install-playwright")
    print(f"  {DIST} --validate")
    print()
    print("Optional branding (paths relative to the exe directory):")
    print(f"  mkdir {DIST.parent}\\assets")
    print(f"  copy assets\\client_logo.png {DIST.parent}\\assets\\")


if __name__ == "__main__":
    main()
