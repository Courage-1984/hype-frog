# --regen-report validation only (after a completed crawl saved a snapshot).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "==> Activating venv" -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Snapshot / report state" -ForegroundColor Cyan
python scripts\_check_snapshot_state.py

Write-Host "==> pytest snapshots + regen_report" -ForegroundColor Cyan
pytest tests\snapshots tests\orchestration\test_regen_report.py -q

Write-Host "==> --regen-report (latest)" -ForegroundColor Cyan
python scripts\_run_regen_report_test.py

$regen1 = Get-ChildItem reports\latest\SEO_AEO_Audit_*_regen_*.xlsx |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $regen1) { Write-Error "Regen workbook missing after latest replay" }

$snapId = python -c @"
from hype_frog.snapshots import list_crawl_snapshots
snaps = list_crawl_snapshots('africanmarketingconfederation.org')
print(snaps[0].snapshot_id if snaps else '')
"@

if ($snapId) {
    Write-Host "==> --regen-report --snapshot-id $snapId" -ForegroundColor Cyan
    python scripts\_run_regen_report_test.py $snapId
}

$original = Get-ChildItem reports\latest\SEO_AEO_Audit_*.xlsx |
    Where-Object { $_.Name -notmatch '_regen_' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

Write-Host "==> Done" -ForegroundColor Green
Write-Host "Original: $($original.Name)"
Write-Host "Regen:    $($regen1.Name)"
