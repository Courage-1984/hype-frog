from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from hype_frog.core import get_logger
from hype_frog.core.models import CheckpointPayload, CrawlResult

logger = get_logger(__name__)


def load_checkpoint(
    checkpoint_file: str,
) -> tuple[list[CrawlResult], set[str], dict[str, Any]]:
    if not os.path.exists(checkpoint_file):
        return [], set(), {}
    with open(checkpoint_file, "r", encoding="utf-8") as handle:
        checkpoint_data = json.load(handle)
    resumed_results = checkpoint_data.get("results", []) or []
    completed_urls = set(checkpoint_data.get("completed_urls", []) or [])
    if not completed_urls:
        completed_urls = {
            r.get("main", {}).get("URL")
            for r in resumed_results
            if r.get("main", {}).get("URL")
        }
    bfs_state = {
        "queue_pending": checkpoint_data.get("queue_pending") or [],
        "queued_set": checkpoint_data.get("queued_set") or [],
        "seed_queue_pending": checkpoint_data.get("seed_queue_pending") or [],
        "seed_phase_active": checkpoint_data.get("seed_phase_active"),
        "crawl_urls_runtime": checkpoint_data.get("crawl_urls_runtime") or [],
    }
    return resumed_results, completed_urls, bfs_state


def save_checkpoint(
    checkpoint_file: str,
    results: list[CrawlResult],
    urls: list[str],
    checkpoint_completed_urls: set[str],
    *,
    bfs_state: dict[str, Any] | None = None,
) -> None:
    completed_urls = [r.get("main", {}).get("URL") for r in results if r.get("main")]
    remaining_urls = [u for u in urls if u not in set(completed_urls)]
    checkpoint_payload: CheckpointPayload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "completed": len(results),
        "total": len(urls) + len(checkpoint_completed_urls),
        "completed_urls": completed_urls,
        "remaining_urls": remaining_urls,
        "results": results,
    }
    payload: dict[str, Any] = dict(checkpoint_payload)
    if bfs_state:
        payload.update(
            {
                "queue_pending": bfs_state.get("queue_pending") or [],
                "queued_set": bfs_state.get("queued_set") or [],
                "seed_queue_pending": bfs_state.get("seed_queue_pending") or [],
                "seed_phase_active": bfs_state.get("seed_phase_active"),
                "crawl_urls_runtime": bfs_state.get("crawl_urls_runtime") or [],
            }
        )
    tmp_path = f"{checkpoint_file}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
    os.replace(tmp_path, checkpoint_file)


def delete_checkpoint(checkpoint_file: str) -> None:
    if os.path.exists(checkpoint_file):
        os.unlink(checkpoint_file)
