from __future__ import annotations

import json
import os
from datetime import datetime

from hype_frog.models import CheckpointPayload, CrawlResult


def load_checkpoint(checkpoint_file: str) -> tuple[list[CrawlResult], set[str]]:
    if not os.path.exists(checkpoint_file):
        return [], set()
    with open(checkpoint_file, "r", encoding="utf-8") as f:
        checkpoint_data = json.load(f)
    resumed_results = checkpoint_data.get("results", []) or []
    completed_urls = set(checkpoint_data.get("completed_urls", []) or [])
    if not completed_urls:
        completed_urls = {
            r.get("main", {}).get("URL")
            for r in resumed_results
            if r.get("main", {}).get("URL")
        }
    return resumed_results, completed_urls


def save_checkpoint(
    checkpoint_file: str,
    results: list[CrawlResult],
    urls: list[str],
    checkpoint_completed_urls: set[str],
) -> None:
    completed_urls = [r.get("main", {}).get("URL") for r in results if r.get("main")]
    remaining_urls = [u for u in urls if u not in set(completed_urls)]
    checkpoint_payload: CheckpointPayload = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "completed": len(results),
        "total": len(urls) + len(checkpoint_completed_urls),
        "completed_urls": completed_urls,
        "remaining_urls": remaining_urls,
        "results": results,
    }
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(checkpoint_payload, f, ensure_ascii=True, indent=2)
