"""Tests for CrawlReplaySnapshot serialisation."""

from __future__ import annotations

import pytest

from hype_frog.snapshots.models import (
    CRAWL_SNAPSHOT_SCHEMA_VERSION,
    CrawlReplaySnapshot,
    SnapshotSchemaError,
)


def _sample_snapshot() -> CrawlReplaySnapshot:
    return CrawlReplaySnapshot(
        snapshot_id="11111111-2222-4333-8444-555555555555",
        domain="example.com",
        run_timestamp="2026-06-28 12:00:00",
        source_output_path="/tmp/SEO_AEO_Audit_example.com_20260628_120000.xlsx",
        main_rows=[
            {
                "URL": "https://example.com/",
                "Extraction State": "complete",
                "SEO Health Score": 80.0,
            }
        ],
        extra_rows=[
            {
                "URL": "https://example.com/",
                "AEO Readiness Score": 70.0,
            }
        ],
        crawl_context={"target_input": "https://example.com/", "full_suite": True},
        enrichment_context={"status_by_url": {}, "sitemap_url_keys": []},
        setup_context={"high_value_slugs": ["contact"]},
    )


def test_crawl_replay_snapshot_round_trip() -> None:
    original = _sample_snapshot()
    restored = CrawlReplaySnapshot.from_dict(original.to_dict())
    assert restored.snapshot_id == original.snapshot_id
    assert restored.domain == original.domain
    assert restored.main_rows[0]["Extraction State"] == "complete"
    assert restored.extra_rows[0]["AEO Readiness Score"] == 70.0
    assert restored.schema_version == CRAWL_SNAPSHOT_SCHEMA_VERSION


def test_crawl_replay_snapshot_rejects_newer_schema() -> None:
    payload = _sample_snapshot().to_dict()
    payload["schema_version"] = CRAWL_SNAPSHOT_SCHEMA_VERSION + 1
    with pytest.raises(SnapshotSchemaError, match="newer than supported"):
        CrawlReplaySnapshot.from_dict(payload)
