Regenerate workbook from saved crawl snapshot (no HTTP/PSI/GSC):

```powershell
$env:HF_REGEN_REPORT = "1"
uv run hype-frog --regen-report
```

Optional: `--snapshot-id <id>` or `HF_SNAPSHOT_ID` to pick a specific snapshot from `.cache/crawl_snapshots.sqlite`.

Use this for reporter-only iteration instead of live crawls.
