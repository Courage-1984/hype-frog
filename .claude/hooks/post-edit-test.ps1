# Runs targeted pytest after edits under tests/ or src/hype_frog/reporter/.
# Claude Code PostToolUse hook — suppresses verbose output (last 20 lines only).

$ErrorActionPreference = 'SilentlyContinue'
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

$testTarget = $null
if ($normalised -match 'tests/([^/]+)/') {
    $layer = $Matches[1]
    $testTarget = "tests/$layer/"
} elseif ($normalised -match 'src/hype_frog/reporter/') {
    $testTarget = 'tests/reporter/'
} else {
    exit 0
}

Push-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
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
