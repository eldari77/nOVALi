$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure([string]$Message) {
    $failures.Add($Message) | Out-Null
}

function Test-TrackedPattern([string]$Pattern, [string]$Description) {
    $matches = git grep -n -I -- $Pattern -- . 2>$null
    if ($LASTEXITCODE -eq 0 -and $matches) {
        Add-Failure "$Description matched:`n$matches"
    }
}

Test-TrackedPattern ("space-" + "based resource " + "extraction") "Forbidden private directive phrase"
Test-TrackedPattern ("space " + "technologies") "Forbidden private directive phrase"
Test-TrackedPattern ("resource " + "extraction and expansion") "Forbidden private directive phrase"
Test-TrackedPattern ("llm_draft_" + "20260529T1755430_5944ecf38282") "Private active workspace id"
Test-TrackedPattern ("OPENAI" + "_API_KEY=") "Raw OpenAI key assignment"
Test-TrackedPattern "sk-[A-Za-z0-9_-]{16,}" "OpenAI-style secret"
Test-TrackedPattern "Bearer [A-Za-z0-9._-]{16,}" "Bearer-token style secret"
Test-TrackedPattern ("C:" + "\\Users\\eLDARi") "Absolute local host path"

$tracked = git ls-files | Where-Object { Test-Path -LiteralPath $_ }
$forbiddenTracked = $tracked | Where-Object {
    $_ -match 'node_modules/' -or
    $_ -match '(^|/)__pycache__/' -or
    $_ -match '\.pyc$' -or
    $_ -match 'directive_inputs/pending_llm/' -or
    $_ -match 'novali-active_workspace/.+/.+' -or
    $_ -match 'runtime_data/logs/.+\.jsonl$' -or
    $_ -match 'operator_state/autonomy/ledgers/.+\.jsonl$' -or
    $_ -match 'novali_disk_spill' -or
    $_ -match '\.env$'
}
if ($forbiddenTracked) {
    Add-Failure "Forbidden tracked files:`n$($forbiddenTracked -join "`n")"
}

if ($failures.Count -gt 0) {
    Write-Error ("Public handoff hygiene failed:`n" + ($failures -join "`n`n"))
    exit 1
}

Write-Host "Public handoff hygiene passed."
