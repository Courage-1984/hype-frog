# Blocks git mutating commands (aligns with git-sovereignty policy).
# Claude Code PreToolUse hook — reads JSON from stdin; exit 2 denies the tool call.

$ErrorActionPreference = 'Stop'
$inputRaw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputRaw)) { exit 0 }

try {
    $payload = $inputRaw | ConvertFrom-Json
} catch {
    exit 0
}

$command = ''
if ($payload.tool_input) {
    if ($payload.tool_input.command) { $command = [string]$payload.tool_input.command }
    elseif ($payload.tool_input.PSObject.Properties['command']) {
        $command = [string]$payload.tool_input.command
    }
}
if (-not $command -and $payload.command) { $command = [string]$payload.command }

$lower = $command.ToLowerInvariant()
$blocked = @(
    'git commit', 'git push', 'git add', 'git rebase', 'git reset',
    'git checkout --', 'git restore', 'git merge', 'git cherry-pick'
)
foreach ($pattern in $blocked) {
    if ($lower -like "*$pattern*") {
        Write-Error "Git sovereignty: blocked '$pattern' in tool command."
        exit 2
    }
}
exit 0
