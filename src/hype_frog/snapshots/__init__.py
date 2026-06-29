"""Public API for crawl snapshot persistence and replay."""

from __future__ import annotations

from hype_frog.snapshots.models import (
    CRAWL_SNAPSHOT_SCHEMA_VERSION,
    CrawlReplaySnapshot,
    SnapshotMeta,
    SnapshotSchemaError,
)
from hype_frog.snapshots.store import (
    list_crawl_snapshots,
    load_crawl_snapshot_by_id,
    load_latest_crawl_snapshot_for_domain,
    open_snapshots_db,
    prune_snapshots_for_domain,
    resolve_snapshots_db_path,
    save_crawl_snapshot,
)

__all__ = [
    "CRAWL_SNAPSHOT_SCHEMA_VERSION",
    "CrawlReplaySnapshot",
    "SnapshotMeta",
    "SnapshotSchemaError",
    "list_crawl_snapshots",
    "load_crawl_snapshot_by_id",
    "load_latest_crawl_snapshot_for_domain",
    "open_snapshots_db",
    "prune_snapshots_for_domain",
    "resolve_snapshots_db_path",
    "save_crawl_snapshot",
]
