"""Build a uv-run distribution bundle under ``dist/``."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Runtime layout copied into each distribution folder.
_BUNDLE_DIRS = ("src", "docs", "scripts")
_BUNDLE_FILES = (
    "README.md",
    "commands.md",
    "pyproject.toml",
    "uv.lock",
    ".env.example",
)


def _read_version(pyproject_path: Path) -> str:
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version ="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def build_distribution(
    *,
    output_root: Path | None = None,
    clean: bool = True,
) -> Path:
    """Copy project assets into ``dist/hype-frog-<version>/``."""
    root = _REPO_ROOT
    version = _read_version(root / "pyproject.toml")
    dist_root = (output_root or root / "dist").resolve()
    bundle_dir = dist_root / f"hype-frog-{version}"

    if clean and bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in _BUNDLE_DIRS:
        source = root / name
        if not source.is_dir():
            raise FileNotFoundError(f"Required bundle directory missing: {source}")
        dest = bundle_dir / name
        shutil.copytree(source, dest)
        copied.append(name)

    for name in _BUNDLE_FILES:
        source = root / name
        if not source.is_file():
            raise FileNotFoundError(f"Required bundle file missing: {source}")
        shutil.copy2(source, bundle_dir / name)
        copied.append(name)

    manifest = {
        "name": "hype-frog",
        "version": version,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "bundle_root": str(bundle_dir),
        "copied": copied,
        "run": "uv sync && uv run hype-frog --help",
    }
    manifest_path = bundle_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return bundle_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build hype-frog distribution bundle")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/dist)",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove an existing bundle folder before copying",
    )
    args = parser.parse_args(argv)

    try:
        bundle = build_distribution(output_root=args.output, clean=not args.no_clean)
    except FileNotFoundError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1

    print(f"Distribution bundle written to: {bundle}")
    print("Verify with: cd <bundle> && uv sync && uv run hype-frog --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
