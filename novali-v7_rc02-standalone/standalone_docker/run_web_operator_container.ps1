$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

$directiveInputs = Join-Path $packageRoot "directive_inputs"
$trustedSources = Join-Path $packageRoot "trusted_sources"
$operatorState = Join-Path $packageRoot "operator_state"
$runtimeState = Join-Path $packageRoot "runtime_data\\state"
$runtimeLogs = Join-Path $packageRoot "runtime_data\\logs"
$runtimeGenerated = Join-Path $packageRoot "runtime_data\\generated"
$runtimeEvidence = Join-Path $packageRoot "runtime_data\\acceptance_evidence"
$activeWorkspace = Join-Path $packageRoot "novali-active_workspace"
$packageDocs = Join-Path $packageRoot "docs"
$packageSamples = Join-Path $packageRoot "samples"
$packageImageDir = Join-Path $packageRoot "image"
$handoffManifest = Join-Path $packageRoot "handoff_layout_manifest.json"
$imageManifest = Join-Path $packageRoot "image\\image_archive_manifest.json"
$readmeFirst = Join-Path $packageRoot "README_FIRST.md"
$loadScript = Join-Path $scriptRoot "load_image_archive.ps1"
$imageTag = "novali-v7-standalone:local"

function Start-LocalPackagedOperator {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is unavailable and Python is not available on PATH. Start Docker Desktop or install Python, then rerun this launcher."
        exit 1
    }
    Write-Warning "Docker is unavailable or unhealthy. Falling back to the packaged local Python operator."
    Push-Location $packageRoot
    try {
        python -m novali_v5.web_operator `
            --host 127.0.0.1 `
            --port 8787 `
            --operator-root $operatorState `
            --state-root $runtimeState `
            --package-root $packageRoot @args
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Test-DockerHealthy {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }
    docker version | Out-Null 2>$null
    return $LASTEXITCODE -eq 0
}

if (-not (Test-DockerHealthy)) {
    Start-LocalPackagedOperator
}

docker image inspect $imageTag | Out-Null 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "NOVALI standalone image is not loaded yet. Loading the packaged archive first..."
    & $loadScript
    if ($LASTEXITCODE -ne 0) {
        if (-not (Test-DockerHealthy)) {
            Start-LocalPackagedOperator
        }
        exit $LASTEXITCODE
    }
}

foreach ($path in @($directiveInputs, $trustedSources, $operatorState, $runtimeState, $runtimeLogs, $runtimeGenerated, $runtimeEvidence, $activeWorkspace)) {
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
Write-Host "Generated outputs: $runtimeGenerated"
Write-Host "Acceptance evidence: $runtimeEvidence"
Write-Host "Active workspace: $activeWorkspace"
Write-Host "Recommended first browser action: use the valid directive sample or download a scaffold, then save runtime policy before launch."
if ($env:OPENAI_API_KEY) {
    Write-Host "Trusted-source credential detected in the current shell session. The raw secret will not be echoed."
}
if ($env:NOVALI_TRUSTED_SOURCE_API_BASE_URL) {
    Write-Host "Trusted-source provider base URL override detected: $($env:NOVALI_TRUSTED_SOURCE_API_BASE_URL)"
}

Push-Location $packageRoot
try {
    docker run --rm `
        -p 127.0.0.1:8787:8787 `
        -v "${packageRoot}:/workspace/novali:ro" `
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
        -v "${runtimeGenerated}:/workspace/novali/runtime_data/generated" `
        -v "${runtimeEvidence}:/workspace/novali/runtime_data/acceptance_evidence" `
        -v "${activeWorkspace}:/workspace/novali/novali-active_workspace" `
        -e NOVALI_OPERATOR_ROOT=/workspace/novali/operator_state `
        -e NOVALI_STATE_ROOT=/workspace/novali/runtime_data/state `
        -e OPENAI_API_KEY `
        -e NOVALI_TRUSTED_SOURCE_API_BASE_URL `
        $imageTag @args
}
finally {
    Pop-Location
}
