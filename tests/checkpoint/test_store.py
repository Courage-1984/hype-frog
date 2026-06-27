"""Checkpoint save/load round-trip tests (D5)."""
from __future__ import annotations

import json
from pathlib import Path

from hype_frog.checkpoint.store import delete_checkpoint, load_checkpoint, save_checkpoint


def _sample_results() -> list[dict]:
    return [
        {
            "main": {"URL": "https://example.com/a", "Status Code": 200},
            "extra": {"URL": "https://example.com/a", "Extraction State": "complete"},
        },
        {
            "main": {"URL": "https://example.com/b", "Status Code": 200},
            "extra": {"URL": "https://example.com/b", "Extraction State": "complete"},
        },
    ]


def test_checkpoint_save_load_round_trip(tmp_path: Path) -> None:
    checkpoint_file = str(tmp_path / "crawl_checkpoint.json")
    results = _sample_results()
    bfs_state = {
        "queue_pending": [("https://example.com/c", 1, "https://example.com/a")],
        "queued_set": ["https://example.com/a", "https://example.com/b", "https://example.com/c"],
        "seed_queue_pending": [],
        "seed_phase_active": False,
        "crawl_urls_runtime": ["https://example.com/a", "https://example.com/b"],
    }
    save_checkpoint(
        checkpoint_file,
        results,
        urls=["https://example.com/a", "https://example.com/b", "https://example.com/c"],
        checkpoint_completed_urls=set(),
        bfs_state=bfs_state,
    )

    loaded_results, completed_urls, loaded_bfs = load_checkpoint(checkpoint_file)
    assert len(loaded_results) == 2
    assert "https://example.com/a" in completed_urls
    assert loaded_bfs["queue_pending"][0][0] == "https://example.com/c"
    assert "https://example.com/c" in loaded_bfs["queued_set"]
    assert loaded_bfs["seed_phase_active"] is False


def test_checkpoint_delete_removes_file(tmp_path: Path) -> None:
    checkpoint_file = str(tmp_path / "crawl_checkpoint.json")
    save_checkpoint(
        checkpoint_file,
        _sample_results(),
        urls=["https://example.com/a"],
        checkpoint_completed_urls=set(),
    )
    assert Path(checkpoint_file).exists()
    delete_checkpoint(checkpoint_file)
    assert not Path(checkpoint_file).exists()


def test_load_missing_checkpoint_returns_empty() -> None:
    results, completed, bfs = load_checkpoint("/nonexistent/path/checkpoint.json")
    assert results == []
    assert completed == set()
    assert bfs == {}


def test_saved_at_is_timezone_aware_iso_string(tmp_path: Path) -> None:
    """saved_at must use timezone-aware ISO format (no naive utcnow)."""
    checkpoint_file = str(tmp_path / "cp.json")
    save_checkpoint(checkpoint_file, _sample_results(), urls=[], checkpoint_completed_urls=set())
    with open(checkpoint_file) as fh:
        payload = json.load(fh)
    saved_at = payload["saved_at"]
    assert isinstance(saved_at, str)
    # Timezone-aware ISO strings include +00:00 suffix (datetime.now(timezone.utc))
    assert "+" in saved_at or saved_at.endswith("Z"), (
        f"saved_at {saved_at!r} has no timezone offset"
    )
    # Must not end with bare 'Z' appended to a naive timestamp (old utcnow pattern)
    # — the new pattern produces +00:00 from isoformat(), not a trailing 'Z'.
    # Either form is acceptable; what is NOT acceptable is no timezone at all.


def test_load_checkpoint_derives_completed_urls_from_results_when_key_missing(
    tmp_path: Path,
) -> None:
    """When completed_urls key is absent, URLs are derived from result main dicts."""
    checkpoint_file = str(tmp_path / "cp_legacy.json")
    payload = {
        "saved_at": "2026-01-01T00:00:00+00:00",
        "completed": 1,
        "total": 1,
        "results": [
            {
                "main": {"URL": "https://example.com/legacy"},
                "extra": {"URL": "https://example.com/legacy"},
            }
        ],
        # intentionally no "completed_urls" key
    }
    with open(checkpoint_file, "w") as fh:
        json.dump(payload, fh)

    results, completed, _bfs = load_checkpoint(checkpoint_file)
    assert results
    assert "https://example.com/legacy" in completed


def test_checkpoint_save_with_zero_results(tmp_path: Path) -> None:
    checkpoint_file = str(tmp_path / "cp_empty.json")
    save_checkpoint(checkpoint_file, [], urls=[], checkpoint_completed_urls=set())
    results, completed, _bfs = load_checkpoint(checkpoint_file)
    assert results == []
    assert completed == set()
