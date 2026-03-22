$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

$directiveInputs = Join-Path $packageRoot "directive_inputs"
$trustedSources = Join-Path $packageRoot "trusted_sources"
$operatorState = Join-Path $packageRoot "operator_state"
$runtimeState = Join-Path $packageRoot "runtime_data\\state"
$runtimeLogs = Join-Path $packageRoot "runtime_data\\logs"
$runtimeEvidence = Join-Path $packageRoot "runtime_data\\acceptance_evidence"
$packageDocs = Join-Path $packageRoot "docs"
$packageSamples = Join-Path $packageRoot "samples"
$packageImageDir = Join-Path $packageRoot "image"
$handoffManifest = Join-Path $packageRoot "handoff_layout_manifest.json"
$imageManifest = Join-Path $packageRoot "image\\image_archive_manifest.json"
$readmeFirst = Join-Path $packageRoot "README_FIRST.md"
$loadScript = Join-Path $scriptRoot "load_image_archive.ps1"
$imageTag = "novali-v5-standalone:local"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not available on PATH. Install/start Docker Desktop first, then rerun this launcher."
    exit 1
}

docker image inspect $imageTag | Out-Null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "NOVALI standalone image is not loaded yet. Loading the packaged archive first..."
    & $loadScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

foreach ($path in @($directiveInputs, $trustedSources, $operatorState, $runtimeState, $runtimeLogs, $runtimeEvidence)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

Write-Host "NOVALI localhost web operator will be available at http://127.0.0.1:8787/"
Write-Host "This slice is intended for local single-operator use only."
Write-Host "Package guide: $readmeFirst"
Write-Host "Package manifest: $handoffManifest"
Write-Host "Image manifest: $imageManifest"
Write-Host "Packaged docs (read-only): $packageDocs"
Write-Host "Packaged samples (read-only): $packageSamples"
Write-Host "Directive inputs: $directiveInputs"
Write-Host "Trusted sources: $trustedSources"
Write-Host "Operator state: $operatorState"
Write-Host "Runtime state: $runtimeState"
Write-Host "Runtime logs: $runtimeLogs"
Write-Host "Acceptance evidence: $runtimeEvidence"
Write-Host "Recommended first browser action: use the valid directive sample or download a scaffold, then save runtime policy before launch."

Push-Location $packageRoot
try {
    docker run --rm `
        -p 127.0.0.1:8787:8787 `
        -v "${readmeFirst}:/workspace/novali/README_FIRST.md:ro" `
        -v "${handoffManifest}:/workspace/novali/handoff_layout_manifest.json:ro" `
        -v "${packageDocs}:/workspace/novali/docs:ro" `
        -v "${packageSamples}:/workspace/novali/samples:ro" `
        -v "${packageImageDir}:/workspace/novali/image:ro" `
        -v "${directiveInputs}:/workspace/novali/directive_inputs" `
        -v "${trustedSources}:/workspace/novali/trusted_sources" `
        -v "${operatorState}:/workspace/novali/operator_state" `
        -v "${runtimeState}:/workspace/novali/runtime_data/state" `
        -v "${runtimeLogs}:/workspace/novali/runtime_data/logs" `
        -v "${runtimeEvidence}:/workspace/novali/runtime_data/acceptance_evidence" `
        -e NOVALI_OPERATOR_ROOT=/workspace/novali/operator_state `
        -e NOVALI_STATE_ROOT=/workspace/novali/runtime_data/state `
        $imageTag @args
}
finally {
    Pop-Location
}
