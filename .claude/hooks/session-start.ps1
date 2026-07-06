# SessionStart hook — read-only git context (branch + last commit).
# Mutating git remains blocked by block-git.ps1 and permissions.deny.

$ErrorActionPreference = 'SilentlyContinue'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $repoRoot
try {
    $branch = & git rev-parse --abbrev-ref HEAD 2>$null
    $commit = & git log -1 --oneline 2>$null
    $status = & git status -sb 2>$null | Select-Object -First 1
    if ($branch) { Write-Output "git branch: $branch" }
    if ($commit) { Write-Output "git HEAD: $commit" }
    if ($status) { Write-Output "git status: $status" }
} finally {
    Pop-Location
}
exit 0
