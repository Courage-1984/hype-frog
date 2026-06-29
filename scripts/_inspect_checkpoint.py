"""Print checkpoint progress for the latest reports/latest *_checkpoint.json."""

from __future__ import annotations

import json
from pathlib import Path

from hype_frog.config import REPORTS_LATEST_DIR

checkpoints = sorted(
    REPORTS_LATEST_DIR.glob("*_checkpoint.json"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
if not checkpoints:
    print("No checkpoint files found.")
    raise SystemExit(0)

path = checkpoints[0]
data = json.loads(path.read_text(encoding="utf-8"))
print(path.name)
print("completed:", data.get("completed"), "total:", data.get("total"))
print("results:", len(data.get("results") or []))
