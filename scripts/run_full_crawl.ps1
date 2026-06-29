# Full crawl with PSI enabled — always activate venv first.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "==> Activating venv" -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Checkpoint state (if any)" -ForegroundColor Cyan
python scripts\_inspect_checkpoint.py

Write-Host "==> Starting full crawl (PSI enabled)" -ForegroundColor Cyan
python scripts\_run_full_crawl_once.py 2>&1 | Tee-Object -FilePath logs\full_crawl_regen_test.log

Write-Host "==> Post-crawl state" -ForegroundColor Cyan
python scripts\_check_snapshot_state.py
