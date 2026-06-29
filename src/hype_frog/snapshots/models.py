"""Crawl replay snapshot models — full post-enrichment row payloads for report regeneration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hype_frog.analysis.delta_models import utc_now_iso

CRAWL_SNAPSHOT_SCHEMA_VERSION: int = 1


class SnapshotSchemaError(ValueError):
    """Raised when a stored snapshot cannot be loaded for the current runtime."""


@dataclass(frozen=True)
class SnapshotMeta:
    snapshot_id: str
    domain: str
    run_timestamp: str
    schema_version: int
    row_count: int
    source_output_path: str | None
    target_input: str
    full_suite: bool
    created_at: float


@dataclass
class CrawlReplaySnapshot:
    snapshot_id: str
    domain: str
    run_timestamp: str
    source_output_path: str | None
    main_rows: list[dict[str, Any]]
    extra_rows: list[dict[str, Any]]
    crawl_context: dict[str, Any]
    enrichment_context: dict[str, Any]
    setup_context: dict[str, Any]
    schema_version: int = CRAWL_SNAPSHOT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "domain": self.domain,
            "run_timestamp": self.run_timestamp,
            "source_output_path": self.source_output_path,
            "main_rows": self.main_rows,
            "extra_rows": self.extra_rows,
            "crawl_context": self.crawl_context,
            "enrichment_context": self.enrichment_context,
            "setup_context": self.setup_context,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CrawlReplaySnapshot:
        schema_version = int(raw.get("schema_version") or 0)
        if schema_version > CRAWL_SNAPSHOT_SCHEMA_VERSION:
            raise SnapshotSchemaError(
                f"Snapshot schema version {schema_version} is newer than supported "
                f"version {CRAWL_SNAPSHOT_SCHEMA_VERSION}."
            )
        if schema_version < 1:
            raise SnapshotSchemaError("Snapshot is missing a valid schema_version.")

        main_rows = raw.get("main_rows") or []
        extra_rows = raw.get("extra_rows") or []
        if not isinstance(main_rows, list) or not isinstance(extra_rows, list):
            raise SnapshotSchemaError("Snapshot main_rows/extra_rows must be lists.")

        crawl_context = raw.get("crawl_context") or {}
        enrichment_context = raw.get("enrichment_context") or {}
        setup_context = raw.get("setup_context") or {}
        if not all(
            isinstance(block, dict)
            for block in (crawl_context, enrichment_context, setup_context)
        ):
            raise SnapshotSchemaError("Snapshot context blocks must be objects.")

        snapshot_id = str(raw.get("snapshot_id") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        if not snapshot_id or not domain:
            raise SnapshotSchemaError("Snapshot is missing snapshot_id or domain.")

        return cls(
            snapshot_id=snapshot_id,
            domain=domain,
            run_timestamp=str(raw.get("run_timestamp") or "").strip() or utc_now_iso(),
            source_output_path=_optional_str(raw.get("source_output_path")),
            main_rows=[row for row in main_rows if isinstance(row, dict)],
            extra_rows=[row for row in extra_rows if isinstance(row, dict)],
            crawl_context=dict(crawl_context),
            enrichment_context=dict(enrichment_context),
            setup_context=dict(setup_context),
            schema_version=schema_version,
        )


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
