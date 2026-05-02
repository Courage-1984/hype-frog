#!/usr/bin/env python3
"""
One-shot repository layout migration for hype-frog.

Dry-run by default. Run with --execute after backing up / committing.

Phases:
  1) Create archive_legacy/ and move legacy root modules + packages into it.
  2) Scaffold src/hype_frog/, data/, secrets/, logs/, reports/*, tests/.
  3) Copy Python packages back from archive_legacy into src/hype_frog/ with
     import rewrites so `hype_frog.*` resolves (zero-logic-move, not rewrite).
  4) Relocate smoke_urls_15.txt and JSON secrets into data/ and secrets/.
  5) Materialize entry_main.py from archived main.py with import fixes.

This script does not delete data: it uses shutil.move into archive_legacy.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


ROOT_FILES_TO_ARCHIVE: tuple[str, ...] = (
    "config.py",
    "main.py",
    "models.py",
    "utils.py",
    "test_excel_engine.py",
)

ROOT_DIRS_TO_ARCHIVE: tuple[str, ...] = (
    ".old",
    "archive",
    "crawler",
    "extractors",
    "pipeline",
    "reporters",
    # Required for parity with main.py (not in original minimal list).
    "core",
    "rules",
    "checkpoint",
)

DATA_FILES: tuple[str, ...] = ("smoke_urls_15.txt",)
SECRET_FILES: tuple[str, ...] = ("client_secrets.json", "token.json")

IMPORT_REWRITE_PAIRS: tuple[tuple[str, str], ...] = (
    ("from checkpoint ", "from hype_frog.checkpoint "),
    ("from checkpoint.", "from hype_frog.checkpoint."),
    ("from config ", "from hype_frog.config "),
    ("from config.", "from hype_frog.config."),
    ("from core ", "from hype_frog.core "),
    ("from core.", "from hype_frog.core."),
    ("from crawler ", "from hype_frog.crawler "),
    ("from crawler.", "from hype_frog.crawler."),
    ("from extractors ", "from hype_frog.extractors "),
    ("from extractors.", "from hype_frog.extractors."),
    ("import extractors\n", "import hype_frog.extractors\n"),
    ("from models ", "from hype_frog.models "),
    ("from models.", "from hype_frog.models."),
    ("from pipeline ", "from hype_frog.pipeline "),
    ("from pipeline.", "from hype_frog.pipeline."),
    ("from rules ", "from hype_frog.rules "),
    ("from rules.", "from hype_frog.rules."),
    ("from reporters ", "from hype_frog.reporter "),
    ("from reporters.", "from hype_frog.reporter."),
    ("from utils ", "from hype_frog.utils "),
    ("from utils.", "from hype_frog.utils."),
    ("import checkpoint\n", "import hype_frog.checkpoint\n"),
)


def _rewrite_imports(text: str) -> str:
    out = text
    for old, new in IMPORT_REWRITE_PAIRS:
        out = out.replace(old, new)
    # Relative imports inside copied reporter package: reporters. -> hype_frog.reporter.
    out = out.replace("from reporters.", "from hype_frog.reporter.")
    out = out.replace("import reporters\n", "import hype_frog.reporter as reporters\n")
    return out


def _copy_tree_filtered(src: Path, dst: Path, *, ignore_names: frozenset[str] | None = None) -> None:
    ignore_names = ignore_names or frozenset()
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.name in ignore_names:
            continue
        target = dst / child.name
        if child.is_dir():
            _copy_tree_filtered(child, target, ignore_names=ignore_names)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def _rewrite_py_tree(tree: Path) -> None:
    for path in tree.rglob("*.py"):
        raw = path.read_text(encoding="utf-8")
        path.write_text(_rewrite_imports(raw), encoding="utf-8", newline="\n")


def _materialize_entry_main(archive: Path, dest: Path) -> None:
    src_main = archive / "main.py"
    if not src_main.is_file():
        return
    body = _rewrite_imports(src_main.read_text(encoding="utf-8"))
    dest.write_text(body, encoding="utf-8", newline="\n")


def _write_stub_main(pkg: Path) -> None:
    stub = '''"""Installed package CLI entry (delegates to migrated main body)."""
from __future__ import annotations

import asyncio

from hype_frog.entry_main import main as _async_main


def run() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
'''
    (pkg / "main.py").write_text(stub, encoding="utf-8", newline="\n")


def _write_engine_facade(crawler_pkg: Path) -> None:
    text = '''"""Async crawler public surface (re-exports; logic lives in sibling modules)."""
from __future__ import annotations

from hype_frog.crawler.client import create_session
from hype_frog.crawler.fetcher import fetch_and_parse
from hype_frog.crawler.gsc_engine import fetch_gsc_page_metrics
from hype_frog.crawler.link_checks import check_url_status_light, check_url_status_light_limited
from hype_frog.crawler.psi_engine import fetch_psi_metrics_batch
from hype_frog.crawler.sitemap import parse_sitemap

__all__ = [
    "create_session",
    "fetch_and_parse",
    "parse_sitemap",
    "check_url_status_light",
    "check_url_status_light_limited",
    "fetch_gsc_page_metrics",
    "fetch_psi_metrics_batch",
]
'''
    (crawler_pkg / "engine.py").write_text(text, encoding="utf-8", newline="\n")


def _ensure_init(path: Path) -> None:
    init = path / "__init__.py"
    if not init.exists():
        init.write_text('"""Package."""\n', encoding="utf-8")


def plan(repo: Path, archive: Path, execute: bool) -> int:
    lines: list[str] = []
    for name in ROOT_FILES_TO_ARCHIVE:
        p = repo / name
        lines.append(f"  MOVE file  {p.relative_to(repo)} -> {archive.relative_to(repo) / name}  exists={p.is_file()}")
    for name in ROOT_DIRS_TO_ARCHIVE:
        p = repo / name
        lines.append(f"  MOVE dir   {p.relative_to(repo)} -> {archive.relative_to(repo) / name}  exists={p.is_dir()}")
    for name in DATA_FILES:
        p = repo / name
        lines.append(f"  MOVE data  {p.relative_to(repo) / name} -> data/{name}  exists={p.is_file()}")
    for name in SECRET_FILES:
        p = repo / name
        lines.append(f"  MOVE secret {p.relative_to(repo) / name} -> secrets/{name}  exists={p.is_file()}")
    action = "EXECUTING" if execute else "DRY-RUN (no changes)"
    print(f"[{action}] repo={repo}\n" + "\n".join(lines))
    return 0


def migrate(repo: Path, execute: bool) -> None:
    archive = repo / "archive_legacy"
    src_pkg = repo / "src" / "hype_frog"
    if not execute:
        plan(repo, archive, execute)
        return

    archive.mkdir(parents=True, exist_ok=True)

    for name in ROOT_FILES_TO_ARCHIVE:
        src = repo / name
        if src.is_file():
            shutil.move(str(src), str(archive / name))

    for name in ROOT_DIRS_TO_ARCHIVE:
        src = repo / name
        if src.is_dir():
            dest = archive / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))

    # Scaffold
    for d in (
        src_pkg,
        src_pkg / "crawler",
        src_pkg / "reporter",
        repo / "data",
        repo / "secrets",
        repo / "logs",
        repo / "reports" / "latest",
        repo / "reports" / "archive",
        repo / "tests",
    ):
        d.mkdir(parents=True, exist_ok=True)

    for keep in (repo / "logs" / ".gitkeep", repo / "data" / ".gitkeep", repo / "secrets" / ".gitkeep"):
        if not keep.exists():
            keep.write_text("", encoding="utf-8")

    # Copy packages from archive into src layout (reporter = old reporters/).
    mappings: tuple[tuple[str, str], ...] = (
        ("crawler", "crawler"),
        ("extractors", "extractors"),
        ("pipeline", "pipeline"),
        ("core", "core"),
        ("rules", "rules"),
        ("checkpoint", "checkpoint"),
        ("reporters", "reporter"),
    )
    for arch_name, pkg_name in mappings:
        src_tree = archive / arch_name
        if not src_tree.is_dir():
            continue
        dst_tree = src_pkg / pkg_name
        if dst_tree.exists():
            shutil.rmtree(dst_tree)
        _copy_tree_filtered(src_tree, dst_tree, ignore_names=frozenset({"__pycache__"}))
        _rewrite_py_tree(dst_tree)

    # models.py as single module
    models_src = archive / "models.py"
    if models_src.is_file():
        shutil.copy2(models_src, src_pkg / "models.py")
        mp = src_pkg / "models.py"
        mp.write_text(_rewrite_imports(mp.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")

    # Central config + utils (new versions should already exist in src; else copy from archive)
    cfg_src = archive / "config.py"
    if cfg_src.is_file() and not (src_pkg / "config.py").exists():
        shutil.copy2(cfg_src, src_pkg / "config.py")
    util_src = archive / "utils.py"
    if util_src.is_file() and not (src_pkg / "utils.py").exists():
        shutil.copy2(util_src, src_pkg / "utils.py")
        _rewrite_py_tree(src_pkg / "utils.py")

    # Materialize async main body + thin CLI wrapper
    _materialize_entry_main(archive, src_pkg / "entry_main.py")
    _write_stub_main(src_pkg)
    _write_engine_facade(src_pkg / "crawler")
    _ensure_init(src_pkg)
    _ensure_init(src_pkg / "crawler")
    _ensure_init(src_pkg / "reporter")
    _ensure_init(src_pkg / "extractors")
    _ensure_init(src_pkg / "pipeline")
    _ensure_init(src_pkg / "core")
    _ensure_init(src_pkg / "rules")
    _ensure_init(src_pkg / "checkpoint")

    # Relocate data / secrets
    data_dir = repo / "data"
    sec_dir = repo / "secrets"
    for name in DATA_FILES:
        p = repo / name
        if p.is_file():
            shutil.move(str(p), str(data_dir / name))
    for name in SECRET_FILES:
        p = repo / name
        if p.is_file():
            shutil.move(str(p), str(sec_dir / name))

    print("Migration complete. Install editable: uv sync && uv pip install -e .")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform moves/copies. Without this flag, only print the plan.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root (default: parent of this script).",
    )
    args = parser.parse_args()
    repo = (args.repo or Path(__file__).resolve().parent).resolve()
    archive = repo / "archive_legacy"
    if not args.execute:
        plan(repo, archive, execute=False)
        print("\nRe-run with --execute to apply.")
        return
    migrate(repo, execute=True)


if __name__ == "__main__":
    main()
