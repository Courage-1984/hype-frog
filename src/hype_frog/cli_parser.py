"""Structured and legacy CLI argument parsing for hype-frog."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from hype_frog.core.run_config import CliRunOverrides, RunConfig

_STRUCTURED_COMMANDS = frozenset({"crawl", "validate", "auth", "setup", "test"})


def _add_shared_crawl_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Cache-first crawl and write_only export (lower peak RSS)",
    )
    parser.add_argument(
        "--max-memory-mb",
        type=int,
        default=None,
        metavar="N",
        help="Abort crawl when process RSS exceeds N megabytes",
    )
    parser.add_argument(
        "--previous-run",
        default=None,
        metavar="PATH",
        help="Previous audit workbook or delta JSON for comparison",
    )
    parser.add_argument(
        "--gsc-url-inspection",
        action="store_true",
        help="Enable GSC URL Inspection for up to 50 qualifying URLs",
    )
    parser.add_argument(
        "--gsc-url-inspection-full",
        action="store_true",
        help="Enable GSC URL Inspection for all qualifying crawled URLs",
    )
    parser.add_argument(
        "--check-og-images",
        action="store_true",
        help="Verify OG image HTTP status and dimensions",
    )
    parser.add_argument(
        "--check-images",
        action="store_true",
        help="Verify content image HTTP status and dimensions",
    )
    parser.add_argument(
        "--show-all-tabs",
        action="store_true",
        help="Export with no tabs hidden (default hides advanced/historical tabs)",
    )
    parser.add_argument(
        "--competitors",
        default=None,
        metavar="DOMAINS",
        help="Comma-separated competitor domains for benchmarking",
    )
    parser.add_argument(
        "--benchmarks",
        action="store_true",
        help="Enable competitor benchmarking when --competitors is set",
    )
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Generate executive summary PDF alongside the workbook",
    )
    parser.add_argument(
        "--regen-report",
        action="store_true",
        help="Regenerate reports from the latest stored crawl snapshot",
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        metavar="UUID",
        help="With --regen-report: replay a specific stored snapshot",
    )
    parser.add_argument(
        "--re-enrich",
        action="store_true",
        help=(
            "With --regen-report: recompute SEO Health / Technical Health / "
            "Copy Score / SEO Score from the snapshot's crawl signals instead "
            "of replaying the frozen enrichment values. No network calls."
        ),
    )
    parser.add_argument(
        "--psi-delay",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Base delay between PageSpeed Insights API calls",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit DEBUG-level messages to the terminal",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce terminal output to WARNING and above",
    )


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="hype-frog technical SEO auditor (legacy flag interface)",
    )
    parser.add_argument(
        "--full-smoke-test",
        action="store_true",
        help="Pre-export integration gate (mocked crawl at sitemap scale)",
    )
    parser.add_argument("--full-smoke-test-fast", action="store_true")
    parser.add_argument("--full-smoke-test-skip-preflight", action="store_true")
    parser.add_argument("--full-smoke-test-skip-pytest", action="store_true")
    parser.add_argument("--full-smoke-test-skip-audit", action="store_true")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Smoke gate: preflight + pytest + 10-URL crawl + workbook audit",
    )
    parser.add_argument("--quick-test-fast", action="store_true")
    parser.add_argument("--quick-test-skip-preflight", action="store_true")
    parser.add_argument("--quick-test-skip-pytest", action="store_true")
    parser.add_argument("--quick-test-skip-audit", action="store_true")
    parser.add_argument("--install-semantic", action="store_true")
    parser.add_argument("--install-playwright", action="store_true")
    parser.add_argument("--gsc-auth", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validate-url", default=None, metavar="URL")
    parser.add_argument("--psi-probe-url", default="https://example.com", metavar="URL")
    _add_shared_crawl_flags(parser)
    return parser


def _build_structured_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hype-frog",
        description="hype-frog technical SEO auditor",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser(
        "crawl",
        help="Run an SEO/AEO audit crawl and export the workbook",
    )
    crawl.add_argument(
        "--url",
        "-u",
        default=None,
        metavar="URL",
        help="Target URL or sitemap path (omit for interactive prompts)",
    )
    crawl.add_argument(
        "--mode",
        "-m",
        choices=("fast", "accurate"),
        default=None,
        help="Crawl engine: fast (HTTP) or accurate (rendered DOM)",
    )
    crawl.add_argument(
        "--max-urls",
        type=int,
        default=None,
        metavar="N",
        help="Maximum URLs to crawl (blank = no limit)",
    )
    crawl.add_argument(
        "--max-psi-urls",
        type=int,
        default=None,
        metavar="N",
        help="Maximum URLs for PSI (0 disables PSI)",
    )
    crawl.add_argument(
        "--inventory-only",
        action="store_true",
        help="Export Main sheet only (skip full diagnostic suite)",
    )
    _add_shared_crawl_flags(crawl)

    validate = subparsers.add_parser(
        "validate",
        help="Validate credentials and API access without crawling",
    )
    validate.add_argument(
        "--url",
        default=None,
        metavar="URL",
        help="Optional crawl target to match against a GSC property",
    )
    validate.add_argument(
        "--psi-probe-url",
        default="https://example.com",
        metavar="URL",
        help="URL used for the live PageSpeed Insights probe",
    )

    auth = subparsers.add_parser("auth", help="Authentication helpers")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    auth_sub.add_parser("gsc", help="Run Google Search Console OAuth bootstrap")

    setup = subparsers.add_parser("setup", help="Install optional runtime components")
    setup_sub = setup.add_subparsers(dest="setup_command", required=True)
    setup_sub.add_parser("semantic", help="Install spaCy en_core_web_sm model")
    setup_sub.add_parser("playwright", help="Install Playwright Chromium browser")

    test = subparsers.add_parser("test", help="Diagnostic smoke gates")
    test_sub = test.add_subparsers(dest="test_command", required=True)
    for name, help_text in (
        ("quick", "Quick smoke gate (~10 URLs)"),
        ("full-smoke", "Full pre-export smoke gate (sitemap scale)"),
    ):
        gate = test_sub.add_parser(name, help=help_text)
        gate.add_argument("--fast", action="store_true", help="Skip preflight and pytest")
        gate.add_argument("--skip-preflight", action="store_true")
        gate.add_argument("--skip-pytest", action="store_true")
        gate.add_argument("--skip-audit", action="store_true")

    return parser


@dataclass(frozen=True)
class ParsedCli:
    """Normalised CLI outcome consumed by ``main.run``."""

    legacy: argparse.Namespace | None = None
    structured: argparse.Namespace | None = None

    @property
    def is_structured(self) -> bool:
        return self.structured is not None


def parse_cli(argv: list[str] | None = None) -> ParsedCli:
    """Parse argv using structured subcommands or the legacy flag surface."""
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] in _STRUCTURED_COMMANDS:
        return ParsedCli(structured=_build_structured_parser().parse_args(args_list))
    return ParsedCli(legacy=_build_legacy_parser().parse_args(args_list))


def legacy_namespace_to_cli_overrides(args: argparse.Namespace) -> CliRunOverrides:
    gsc_inspection: str | None = None
    if getattr(args, "gsc_url_inspection_full", False):
        gsc_inspection = "full"
    elif getattr(args, "gsc_url_inspection", False):
        gsc_inspection = "limited"
    if getattr(args, "verbose", False) and getattr(args, "quiet", False):
        raise SystemExit("Cannot combine --verbose and --quiet.")
    return CliRunOverrides(
        competitors=getattr(args, "competitors", None),
        benchmarks=getattr(args, "benchmarks", False),
        export_pdf=getattr(args, "export_pdf", False),
        check_og_images=getattr(args, "check_og_images", False),
        check_content_images=getattr(args, "check_images", False),
        previous_run=getattr(args, "previous_run", None),
        gsc_url_inspection=gsc_inspection,
        max_memory_mb=getattr(args, "max_memory_mb", None),
        streaming=getattr(args, "streaming", False),
        regen_report=getattr(args, "regen_report", False),
        snapshot_id=getattr(args, "snapshot_id", None),
        re_enrich=getattr(args, "re_enrich", False),
        verbose=getattr(args, "verbose", False),
        quiet=getattr(args, "quiet", False),
        show_all_tabs=getattr(args, "show_all_tabs", False),
    )


def structured_crawl_run_config(args: argparse.Namespace) -> RunConfig | None:
    """Build a non-interactive ``RunConfig`` when ``crawl --url`` is supplied."""
    if not args.url:
        return None
    crawl_mode = args.mode or "accurate"
    return RunConfig(
        target_input=str(args.url).strip(),
        max_urls=args.max_urls,
        max_psi_urls=args.max_psi_urls,
        high_value_slugs=[],
        crawl_mode=crawl_mode,
        render_wait_ms=4000 if crawl_mode == "accurate" else 1000,
        selector_wait_ms=3000 if crawl_mode == "accurate" else 500,
        workers=3,
        request_delay=0.0,
        full_suite=not args.inventory_only,
        previous_audit_path=args.previous_run or "",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=True,
        check_og_images=args.check_og_images,
        check_content_images=args.check_images,
        gsc_url_inspection=(
            "full"
            if args.gsc_url_inspection_full
            else "limited"
            if args.gsc_url_inspection
            else None
        ),
        max_memory_mb=args.max_memory_mb,
        streaming=args.streaming,
        export_pdf=args.export_pdf,
        hide_advanced_tabs=not getattr(args, "show_all_tabs", False),
    )


__all__ = [
    "ParsedCli",
    "legacy_namespace_to_cli_overrides",
    "parse_cli",
    "structured_crawl_run_config",
]
