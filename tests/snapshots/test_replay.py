"""Tests for replay reconstruction helpers."""

from __future__ import annotations

import pytest

from hype_frog.core.file_utils import build_regen_output_filename
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.snapshots.models import CrawlReplaySnapshot
from hype_frog.core.crawl_log import CrawlLogEntry
from hype_frog.crawler.robots_mapping import build_robot_parser
from hype_frog.snapshots.replay import (
    ReplaySnapshotError,
    _crawl_log_entries_from_json,
    _crawl_log_entries_to_json,
    _robots_by_domain_from_json,
    _robots_by_domain_to_json,
    assert_snapshot_domain_matches,
    replay_from_snapshot,
    resolve_snapshot_domain,
)


def _minimal_setup() -> RunSetup:
    return RunSetup(
        target_input="https://example.com/",
        max_urls=None,
        max_psi_urls=None,
        high_value_slugs=["contact"],
        crawl_mode="fast",
        render_wait_ms=0,
        selector_wait_ms=0,
        workers_preset=None,
        request_delay_preset=None,
        full_suite_preset=True,
        hide_advanced_tabs_preset=None,
        previous_audit_path_preset=None,
        checkpoint_every_preset=None,
        resume_checkpoint_mode="prompt",
        check_external_link_status=True,
    )


def _snapshot(domain: str = "example.com") -> CrawlReplaySnapshot:
    return CrawlReplaySnapshot(
        snapshot_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        domain=domain,
        run_timestamp="2026-06-28 12:00:00",
        source_output_path="reports/latest/SEO_AEO_Audit_example.com_20260628_120000.xlsx",
        main_rows=[
            {"URL": "https://example.com/", "Extraction State": "complete"},
            {"URL": "https://example.com/about", "Extraction State": "partial"},
        ],
        extra_rows=[
            {"URL": "https://example.com/"},
            {"URL": "https://example.com/about"},
        ],
        crawl_context={
            "target_input": "https://example.com/",
            "crawl_urls": ["https://example.com/", "https://example.com/about"],
            "full_suite": True,
            "workers": 3,
            "request_delay": 1.0,
            "previous_audit_path": "",
            "checkpoint_every": 0,
            "check_external_link_status": True,
            "crawl_completed": True,
            "source_label": "example.com",
            "sitemap_meta": {},
            "sitemap_files_meta": {},
        },
        enrichment_context={"status_by_url": {}, "sitemap_url_keys": []},
        setup_context={"high_value_slugs": ["contact"]},
    )


def test_resolve_snapshot_domain_from_url_and_sitemap() -> None:
    assert resolve_snapshot_domain("https://www.example.com/page") == "example.com"
    assert (
        resolve_snapshot_domain("https://example.com/sitemap.xml") == "example.com"
    )


def test_replay_from_snapshot_reconstructs_rows() -> None:
    snapshot = _snapshot()
    regen_path = build_regen_output_filename(
        snapshot.source_output_path or "replay.xlsx",
        snapshot.snapshot_id,
    )
    crawl_result, enrichment = replay_from_snapshot(
        snapshot,
        _minimal_setup(),
        output_filename=regen_path,
    )
    assert crawl_result.output_filename == regen_path
    assert crawl_result.output_filename != snapshot.source_output_path
    assert len(enrichment.typed_main_rows) == 2
    assert enrichment.typed_main_rows[0].values["Extraction State"] == "complete"


def test_crawl_log_entry_round_trip_json() -> None:
    entries = [
        CrawlLogEntry(
            timestamp="2026-06-28 12:00:00 UTC",
            url="https://example.com/",
            phase="crawl",
            error_type="Timeout",
            error_detail="slow",
            recovery_action="retry",
        )
    ]
    payload = _crawl_log_entries_to_json(entries)
    restored = _crawl_log_entries_from_json(payload)
    assert restored is not None
    assert len(restored) == 1
    assert restored[0].error_type == "Timeout"


def test_robots_by_domain_round_trip_json() -> None:
    robots_text = "User-agent: *\nDisallow: /private\n"
    payload = _robots_by_domain_to_json(
        {
            "https://example.com": {
                "robots_text": robots_text,
                "robots_accessible": True,
                "robots_status": 200,
                "parser": build_robot_parser(robots_text),
            }
        }
    )
    restored = _robots_by_domain_from_json(payload)
    assert restored is not None
    entry = restored["https://example.com"]
    assert entry["parser"] is not None
    assert entry["parser"].can_fetch("*", "https://example.com/private/page") is False


def test_assert_snapshot_domain_mismatch_raises() -> None:
    snapshot = _snapshot(domain="other.com")
    with pytest.raises(ReplaySnapshotError, match="does not match target"):
        assert_snapshot_domain_matches(snapshot, "https://example.com/")
