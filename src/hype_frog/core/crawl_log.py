"""Structured crawl / enrichment error log for workbook export (D7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class CrawlLogEntry:
    timestamp: str
    url: str
    phase: str
    error_type: str
    error_detail: str
    recovery_action: str = ""


CRAWL_LOG_COLUMNS: tuple[str, ...] = (
    "Timestamp",
    "URL",
    "Phase",
    "Error Type",
    "Error Detail",
    "Recovery Action Taken",
)


class CrawlLogCollector:
    """Append-only collector for errors and warnings during a run."""

    def __init__(self) -> None:
        self.entries: list[CrawlLogEntry] = []

    def record(
        self,
        *,
        url: str,
        phase: str,
        error_type: str,
        error_detail: str,
        recovery_action: str = "",
        timestamp: str | None = None,
    ) -> None:
        detail = str(error_detail or "").strip()
        if not detail and not error_type:
            return
        self.entries.append(
            CrawlLogEntry(
                timestamp=timestamp
                or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                url=str(url or "").strip(),
                phase=str(phase or "").strip(),
                error_type=str(error_type or "").strip(),
                error_detail=detail,
                recovery_action=str(recovery_action or "").strip(),
            )
        )

    def to_row_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "Timestamp": entry.timestamp,
                "URL": entry.url,
                "Phase": entry.phase,
                "Error Type": entry.error_type,
                "Error Detail": entry.error_detail,
                "Recovery Action Taken": entry.recovery_action or None,
            }
            for entry in self.entries
        ]


def crawl_log_sheet_rows(entries: list[CrawlLogEntry] | None) -> list[dict[str, Any]]:
    """Workbook rows for the Crawl Log sheet."""
    if not entries:
        return [
            {
                "Timestamp": None,
                "URL": None,
                "Phase": "Summary",
                "Error Type": "None",
                "Error Detail": "No crawl errors or warnings recorded for this run.",
                "Recovery Action Taken": None,
            }
        ]
    collector = CrawlLogCollector()
    collector.entries.extend(entries)
    return collector.to_row_dicts()


__all__ = [
    "CRAWL_LOG_COLUMNS",
    "CrawlLogCollector",
    "CrawlLogEntry",
    "crawl_log_sheet_rows",
]
