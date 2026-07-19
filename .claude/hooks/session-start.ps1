# SessionStart — git context + surface map (injected every mode: Plan / acceptEdits / auto).
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

Write-Output @"
hype-frog Claude surfaces (available in Plan and acceptEdits/auto):
  agents: explore-layer | reporter-reviewer | rules-auditor | contract-guardian | test-triager | doc-drift-checker
  skills: quick-verify | reporter-change | add-row-field | doc-sync | add-issue-rule | add-workbook-sheet | layer-pytest
  commands: /validate /quick-test /smoke-test /regen-report /layer-test /reporter-test /preflight /new-issue /new-sheet
  workflows: /layer-boundary-audit /reporter-sheet-lock-audit
  Plan mode = research only (no Edit/Write). acceptEdits/auto = edit allowed; git mutate still denied.
  See .claude/rules/session-modes.md
"@

exit 0
