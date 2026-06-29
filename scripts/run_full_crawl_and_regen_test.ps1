# Full crawl (PSI enabled) + --regen-report validation — PowerShell only.
# Usage: .\scripts\run_full_crawl_and_regen_test.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "==> Activating venv" -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Preflight: snapshot / report state" -ForegroundColor Cyan
python scripts\_check_snapshot_state.py

Write-Host "==> Full crawl (PSI enabled, max_psi_urls=None)" -ForegroundColor Cyan
python scripts\_run_full_crawl_once.py 2>&1 | Tee-Object -FilePath logs\full_crawl_regen_test.log

Write-Host "==> Post-crawl snapshot state" -ForegroundColor Cyan
python scripts\_check_snapshot_state.py

$env:HF_REGEN_REPORT = "0"
$latest = Get-ChildItem reports\latest\SEO_AEO_Audit_*.xlsx |
    Where-Object { $_.Name -notmatch '_regen_' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latest) {
    Write-Error "No crawl workbook found under reports\latest"
}

Write-Host "==> --regen-report (latest snapshot)" -ForegroundColor Cyan
python scripts\_run_regen_report_test.py

$regenLatest = Get-ChildItem reports\latest\SEO_AEO_Audit_*_regen_*.xlsx |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $regenLatest) {
    Write-Error "No regen workbook produced"
}

$snapId = python -c "from hype_frog.snapshots import list_crawl_snapshots; s=list_crawl_snapshots('africanmarketingconfederation.org'); print(s[0].snapshot_id if s else '')"
if ($snapId) {
    Write-Host "==> --regen-report --snapshot-id $snapId" -ForegroundColor Cyan
    python scripts\_run_regen_report_test.py $snapId
}

Write-Host "==> pytest: snapshots + regen_report" -ForegroundColor Cyan
pytest tests\snapshots tests\orchestration\test_regen_report.py -q

Write-Host "==> Done. Original: $($latest.Name)  Regen: $($regenLatest.Name)" -ForegroundColor Green
