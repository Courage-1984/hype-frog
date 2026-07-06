# Runs targeted pytest after edits under tests/ or src/hype_frog/<layer>/.
# Set HF_CLAUDE_HOOK_TEST=0 to disable. PostToolUse — last 20 lines only.

$ErrorActionPreference = 'SilentlyContinue'
if ($env:HF_CLAUDE_HOOK_TEST -eq '0') { exit 0 }

$inputRaw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputRaw)) { exit 0 }

$filePath = ''
try {
    $payload = $inputRaw | ConvertFrom-Json
    if ($payload.tool_input.file_path) { $filePath = [string]$payload.tool_input.file_path }
    elseif ($payload.tool_input.path) { $filePath = [string]$payload.tool_input.path }
} catch {
    exit 0
}

if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }
$normalised = $filePath -replace '\\', '/'

$layerMap = @{
    'src/hype_frog/reporter/'     = 'tests/reporter/'
    'src/hype_frog/crawler/'      = 'tests/crawler/'
    'src/hype_frog/orchestration/' = 'tests/orchestration/'
    'src/hype_frog/rules/'        = 'tests/rules/'
    'src/hype_frog/analysis/'     = 'tests/analysis/'
    'src/hype_frog/pipeline/'     = 'tests/pipeline/'
    'src/hype_frog/extractors/'   = 'tests/extractors/'
    'src/hype_frog/core/'         = 'tests/core/'
    'src/hype_frog/validators/'   = 'tests/validators/'
    'src/hype_frog/checkpoint/'   = 'tests/checkpoint/'
    'src/hype_frog/snapshots/'    = 'tests/snapshots/'
    'src/hype_frog/diagnostics/'  = 'tests/diagnostics/'
}

$testTarget = $null
if ($normalised -match 'tests/([^/]+)/') {
    $testTarget = "tests/$($Matches[1])/"
} else {
    foreach ($prefix in $layerMap.Keys) {
        if ($normalised -like "*$prefix*") {
            $testTarget = $layerMap[$prefix]
            break
        }
    }
    if (-not $testTarget) {
        if ($normalised -match '(^|/)(config(_defaults|_loader)?\.py)') {
            $testTarget = 'tests/config/'
        }
    }
}

if (-not $testTarget) { exit 0 }

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $repoRoot
try {
    $output = & uv run pytest $testTarget -q --tb=line --maxfail=3 2>&1
    if ($output) {
        $lines = @($output)
        $tail = if ($lines.Count -gt 20) { $lines[-20..-1] } else { $lines }
        $tail | ForEach-Object { Write-Output $_ }
    }
} finally {
    Pop-Location
}
exit 0
