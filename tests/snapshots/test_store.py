"""Tests for crawl snapshot SQLite store."""

from __future__ import annotations

from pathlib import Path

import pytest

from hype_frog.snapshots.models import CrawlReplaySnapshot
from hype_frog.snapshots.store import (
    list_crawl_snapshots,
    load_crawl_snapshot_by_id,
    load_latest_crawl_snapshot_for_domain,
    open_snapshots_db,
    prune_snapshots_for_domain,
    resolve_snapshots_db_path,
    save_crawl_snapshot,
)


def _snapshot(
    snapshot_id: str,
    *,
    domain: str = "example.com",
    url: str = "https://example.com/",
) -> CrawlReplaySnapshot:
    return CrawlReplaySnapshot(
        snapshot_id=snapshot_id,
        domain=domain,
        run_timestamp="2026-06-28 12:00:00",
        source_output_path=f"/tmp/{snapshot_id}.xlsx",
        main_rows=[{"URL": url, "Extraction State": "complete"}],
        extra_rows=[{"URL": url}],
        crawl_context={"target_input": url, "full_suite": True},
        enrichment_context={"status_by_url": {}, "sitemap_url_keys": []},
        setup_context={},
    )


@pytest.fixture
def snapshots_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "crawl_snapshots.sqlite"
    monkeypatch.setattr(
        "hype_frog.snapshots.store.resolve_snapshots_db_path",
        lambda: db_path,
    )
    return db_path


def test_save_load_latest_and_list(snapshots_db: Path) -> None:
    first = _snapshot("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    second = _snapshot("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    save_crawl_snapshot(first)
    save_crawl_snapshot(second)

    latest = load_latest_crawl_snapshot_for_domain("example.com")
    assert latest is not None
    assert latest.snapshot_id == second.snapshot_id

    listed = list_crawl_snapshots("example.com")
    assert len(listed) == 2
    assert listed[0].snapshot_id == second.snapshot_id


def test_load_missing_domain_returns_none(snapshots_db: Path) -> None:
    assert load_latest_crawl_snapshot_for_domain("missing.example") is None


def test_load_by_id_and_corrupt_payload(snapshots_db: Path) -> None:
    snapshot = _snapshot("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    save_crawl_snapshot(snapshot)
    loaded = load_crawl_snapshot_by_id(snapshot.snapshot_id)
    assert loaded is not None
    assert loaded.main_rows[0]["Extraction State"] == "complete"

    conn = open_snapshots_db(snapshots_db)
    conn.execute(
        "UPDATE crawl_snapshots SET payload_json = ? WHERE snapshot_id = ?",
        ("not-json", snapshot.snapshot_id),
    )
    conn.commit()
    conn.close()
    assert load_crawl_snapshot_by_id(snapshot.snapshot_id) is None


def test_prune_retention_keeps_latest_only(snapshots_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hype_frog.snapshots.store.get_hf_snapshot_retention_per_domain",
        lambda: 2,
    )
    for index in range(4):
        save_crawl_snapshot(
            _snapshot(f"{index:08d}-0000-4000-8000-0000000000{index:02d}")
        )
    remaining = list_crawl_snapshots("example.com")
    assert len(remaining) == 2
    deleted = prune_snapshots_for_domain("example.com", keep_n=1)
    assert deleted == 1
    assert len(list_crawl_snapshots("example.com")) == 1


def test_resolve_snapshots_db_path_default_exists() -> None:
    path = resolve_snapshots_db_path()
    assert path.name == "crawl_snapshots.sqlite"
