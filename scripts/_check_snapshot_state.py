"""Print latest reports and crawl snapshot store status."""

from __future__ import annotations

from pathlib import Path

from hype_frog.config import REPORTS_LATEST_DIR
from hype_frog.snapshots import list_crawl_snapshots, resolve_snapshots_db_path

print("reports/latest:")
for path in sorted(REPORTS_LATEST_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
    print(f"  {path.name}  ({path.stat().st_size} bytes)")

db = resolve_snapshots_db_path()
print(f"\nsnapshot db: {db} (exists={db.exists()})")
snaps = list_crawl_snapshots()
print(f"snapshots: {len(snaps)}")
for meta in snaps[:5]:
    print(f"  {meta.snapshot_id}  domain={meta.domain}  rows={meta.row_count}  at={meta.run_timestamp}")
