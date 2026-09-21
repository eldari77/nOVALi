$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure([string]$Message) {
    $failures.Add($Message) | Out-Null
}

function Test-PublicPattern([string]$Pattern, [string]$Description) {
    $matches = rg -n -I --pcre2 --glob "!**/.git/**" --glob "!**/node_modules/**" --glob "!**/*.tar" -- $Pattern $repoRoot 2>$null
    if ($LASTEXITCODE -eq 0 -and $matches) {
        Add-Failure "$Description matched:`n$matches"
    }
}

Test-PublicPattern ("space-" + "based resource " + "extraction") "Forbidden private directive phrase"
Test-PublicPattern ("space " + "technologies") "Forbidden private directive phrase"
Test-PublicPattern ("resource " + "extraction and expansion") "Forbidden private directive phrase"
Test-PublicPattern ("llm_draft_" + "20260529T1755430_5944ecf38282") "Private active workspace id"
Test-PublicPattern ("OPENAI" + "_API_KEY=") "Raw OpenAI key assignment"
Test-PublicPattern "(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}" "OpenAI-style secret"
Test-PublicPattern "Bearer [A-Za-z0-9._-]{16,}" "Bearer-token style secret"
Test-PublicPattern ("C:" + "\\Users\\eLDARi") "Absolute local host path"

$publicFiles = Get-ChildItem -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\.git\\' -and $_.FullName -notmatch '\\node_modules\\' } | ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1).Replace('\\', '/') }
$forbiddenTracked = $publicFiles | Where-Object {
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
    Add-Failure "Forbidden public files:`n$($forbiddenTracked -join "`n")"
}

if ($failures.Count -gt 0) {
    Write-Error ("Public handoff hygiene failed:`n" + ($failures -join "`n`n"))
    exit 1
}

Write-Host "Public handoff hygiene passed."
exit 0
