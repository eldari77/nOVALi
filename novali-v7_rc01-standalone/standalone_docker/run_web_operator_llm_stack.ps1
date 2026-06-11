param(
    [string]$Model = $(if ($env:NOVALI_LOCAL_LLM_MODEL) { $env:NOVALI_LOCAL_LLM_MODEL } else { "llama3.1" }),
    [switch]$SkipModelPull,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$composeFile = Join-Path $packageRoot "docker-compose.llm.yml"

$directiveInputs = Join-Path $packageRoot "directive_inputs"
$trustedSources = Join-Path $packageRoot "trusted_sources"
$operatorState = Join-Path $packageRoot "operator_state"
$runtimeState = Join-Path $packageRoot "runtime_data\state"
$runtimeLogs = Join-Path $packageRoot "runtime_data\logs"
$runtimeGenerated = Join-Path $packageRoot "runtime_data\generated"
$runtimeEvidence = Join-Path $packageRoot "runtime_data\acceptance_evidence"
$activeWorkspace = Join-Path $packageRoot "novali-active_workspace"

function Test-DockerHealthy {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }
    docker version | Out-Null 2>$null
    return $LASTEXITCODE -eq 0
}

function Invoke-Compose {
    docker compose -f $composeFile @args
}

if (-not (Test-DockerHealthy)) {
    Write-Error "Docker is unavailable or unhealthy. Start Docker Desktop, then rerun this launcher."
    exit 1
}

foreach ($path in @($directiveInputs, $trustedSources, $operatorState, $runtimeState, $runtimeLogs, $runtimeGenerated, $runtimeEvidence, $activeWorkspace)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$env:NOVALI_LOCAL_LLM_MODEL = $Model

Push-Location $packageRoot
try {
    Write-Host "Starting NOVALI + local Ollama stack."
    Write-Host "NOVALI: http://127.0.0.1:8787/"
    Write-Host "Ollama is internal to the compose network as http://ollama:11434."
    Write-Host "Model: $Model"

    if ($NoBuild) {
        Invoke-Compose up -d ollama novali
    }
    else {
        Invoke-Compose up -d --build ollama novali
    }

    if (-not $SkipModelPull) {
        Write-Host "Ensuring Ollama model is available: $Model"
        Invoke-Compose --profile model-pull run --rm -T ollama-model
    }

    Write-Host "Stack status:"
    Invoke-Compose ps
    Write-Host "Open http://127.0.0.1:8787/shell and use Ask Novali > Refresh provider."
}
finally {
    Pop-Location
}
