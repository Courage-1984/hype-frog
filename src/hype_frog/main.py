"""Installed package CLI entry (delegates to migrated main body)."""

from __future__ import annotations

import argparse
import asyncio
import os

from hype_frog.config import apply_runtime_override, load_environment
from hype_frog.core.run_config import FULL_SMOKE_SYNTHETIC_URL_COUNT
from hype_frog.core.integration_validator import run_validation_cli
from hype_frog.core.quick_test import QuickTestOptions, run_quick_test_gate
from hype_frog.core.full_smoke_test import FullSmokeOptions, run_full_smoke_gate
from hype_frog.app_orchestrator import main as _async_main
from hype_frog.crawler.gsc_engine import ensure_gsc_oauth_token
from hype_frog.extractors.semantic_setup import install_semantic_model


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="hype-frog technical SEO auditor")
    parser.add_argument(
        "--full-smoke-test",
        action="store_true",
        help=(
            "Pre-export integration gate: OAuth + live PSI preflight, pytest, "
            f"~{FULL_SMOKE_SYNTHETIC_URL_COUNT}-URL uncapped sitemap simulation "
            "(mocked crawl; real enrichment + export + workbook audit)"
        ),
    )
    parser.add_argument(
        "--full-smoke-test-fast",
        action="store_true",
        help="Same as --full-smoke-test but skip preflight and pytest",
    )
    parser.add_argument(
        "--full-smoke-test-skip-preflight",
        action="store_true",
        help="With --full-smoke-test: skip GSC/PSI preflight checks",
    )
    parser.add_argument(
        "--full-smoke-test-skip-pytest",
        action="store_true",
        help="With --full-smoke-test: skip pytest regression subset",
    )
    parser.add_argument(
        "--full-smoke-test-skip-audit",
        action="store_true",
        help="With --full-smoke-test: skip post-export workbook audit",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help=(
            "Comprehensive smoke gate: preflight checks, focused pytest, "
            "10-URL sitemap crawl (Playwright + full suite), workbook audit"
        ),
    )
    parser.add_argument(
        "--quick-test-fast",
        action="store_true",
        help="Same crawl/export as --quick-test but skip preflight and pytest",
    )
    parser.add_argument(
        "--quick-test-skip-preflight",
        action="store_true",
        help="With --quick-test: skip GSC/PSI preflight checks",
    )
    parser.add_argument(
        "--quick-test-skip-pytest",
        action="store_true",
        help="With --quick-test: skip focused pytest regression subset",
    )
    parser.add_argument(
        "--quick-test-skip-audit",
        action="store_true",
        help="With --quick-test: skip post-export workbook audit",
    )
    parser.add_argument(
        "--install-semantic",
        action="store_true",
        help=(
            "Install/verify the spaCy en_core_web_sm model "
            "(requires: uv sync --extra semantic)"
        ),
    )
    parser.add_argument(
        "--gsc-auth",
        action="store_true",
        help=(
            "Trigger Google Search Console OAuth flow only and create/refresh "
            "secrets/token.json from secrets/client_secrets.json"
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "Validate GSC OAuth files, PSI API key, and optional LLM keys "
            "without running a crawl"
        ),
    )
    parser.add_argument(
        "--validate-url",
        default=None,
        metavar="URL",
        help=(
            "When used with --validate, check that this crawl target matches a "
            "visible Search Console property (e.g. https://example.com/)"
        ),
    )
    parser.add_argument(
        "--psi-probe-url",
        default="https://example.com",
        metavar="URL",
        help="URL used for the live PageSpeed Insights probe during --validate",
    )
    parser.add_argument(
        "--check-og-images",
        action="store_true",
        help=(
            "Fetch OG images to verify HTTP status and dimensions "
            "(extra request per page with og:image)"
        ),
    )
    parser.add_argument(
        "--previous-run",
        default=None,
        metavar="PATH",
        help=(
            "Path to a previous audit workbook (.xlsx) or delta summary JSON "
            "for DeltaFromPreviousRun comparison"
        ),
    )
    parser.add_argument(
        "--gsc-url-inspection",
        action="store_true",
        help=(
            "Enable GSC URL Inspection API for up to 50 qualifying URLs "
            "(indexable, 200 OK, zero Search Analytics impressions)"
        ),
    )
    parser.add_argument(
        "--gsc-url-inspection-full",
        action="store_true",
        help="Enable GSC URL Inspection for all qualifying crawled URLs (expensive)",
    )
    parser.add_argument(
        "--max-memory-mb",
        type=int,
        default=None,
        metavar="N",
        help="Abort crawl when process RSS exceeds N megabytes",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Cache-first crawl writes (reduces in-memory row duplication during fetch)",
    )
    parser.add_argument(
        "--check-images",
        action="store_true",
        help=(
            "Fetch content images to verify HTTP status, dimensions, and oversized files "
            "(extra request per unique image URL)"
        ),
    )
    parser.add_argument(
        "--competitors",
        default=None,
        metavar="DOMAINS",
        help=(
            "Comma-separated competitor domains for optional benchmark sampling "
            "(e.g. example.com,competitor.co.uk)"
        ),
    )
    parser.add_argument(
        "--benchmarks",
        action="store_true",
        help="Enable competitor benchmarking when --competitors is also set",
    )
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help=(
            "Generate a two-page executive summary PDF alongside the workbook "
            "(_executive_summary.pdf)"
        ),
    )
    parser.add_argument(
        "--psi-delay",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Base delay between PageSpeed Insights API calls (default: 2.5, with jitter)",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    load_environment()
    if args.psi_delay is not None and args.psi_delay >= 0:
        apply_runtime_override("PSI_BASE_DELAY_SECONDS", args.psi_delay)
    if args.validate:
        raise SystemExit(
            run_validation_cli(
                target_url=args.validate_url,
                psi_probe_url=args.psi_probe_url,
            )
        )
    if args.install_semantic:
        ok, message = install_semantic_model()
        print(message)
        raise SystemExit(0 if ok else 1)
    if args.gsc_auth:
        ok, token_path = ensure_gsc_oauth_token()
        if ok:
            print(f"GSC OAuth token ready: {token_path}")
        else:
            print(
                "GSC OAuth token bootstrap failed. Ensure "
                "secrets/client_secrets.json exists and re-run --gsc-auth."
            )
        return
    if args.full_smoke_test or args.full_smoke_test_fast:
        smoke_options = FullSmokeOptions(
            skip_preflight=args.full_smoke_test_fast or args.full_smoke_test_skip_preflight,
            skip_pytest=args.full_smoke_test_fast or args.full_smoke_test_skip_pytest,
            skip_workbook_audit=args.full_smoke_test_skip_audit,
        )
        raise SystemExit(asyncio.run(run_full_smoke_gate(smoke_options)))
    if args.quick_test or args.quick_test_fast:
        options = QuickTestOptions(
            skip_preflight=args.quick_test_fast or args.quick_test_skip_preflight,
            skip_pytest=args.quick_test_fast or args.quick_test_skip_pytest,
            skip_workbook_audit=args.quick_test_skip_audit,
        )
        raise SystemExit(asyncio.run(run_quick_test_gate(options)))
    if args.competitors:
        os.environ["HF_COMPETITORS"] = args.competitors
    elif args.benchmarks:
        os.environ.setdefault("HF_COMPETITORS", "")
    if args.export_pdf:
        os.environ["HF_EXPORT_PDF"] = "1"
    if args.check_og_images:
        os.environ["CHECK_OG_IMAGES"] = "1"
    if args.check_images:
        os.environ["CHECK_CONTENT_IMAGES"] = "1"
    if args.previous_run:
        os.environ["HF_PREVIOUS_AUDIT_PATH"] = args.previous_run
    if args.gsc_url_inspection_full:
        os.environ["GSC_URL_INSPECTION"] = "full"
    elif args.gsc_url_inspection:
        os.environ["GSC_URL_INSPECTION"] = "limited"
    if args.max_memory_mb is not None and args.max_memory_mb > 0:
        os.environ["HF_MAX_MEMORY_MB"] = str(args.max_memory_mb)
    if args.streaming:
        os.environ["HF_STREAMING"] = "1"
    asyncio.run(_async_main(None))


if __name__ == "__main__":
    run()
