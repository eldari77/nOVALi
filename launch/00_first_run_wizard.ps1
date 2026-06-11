$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$packageRoot = Join-Path $repoRoot "novali-v7_rc01-standalone"
$shellUrl = "http://127.0.0.1:8787/shell"
$imageTag = "novali-v7-standalone:local"
$imageArchive = Join-Path $packageRoot "image\novali-v7-standalone.tar"
$loadScript = Join-Path $packageRoot "standalone_docker\load_image_archive.ps1"
$runScript = Join-Path $packageRoot "standalone_docker\run_web_operator_container.ps1"

function Test-DockerHealthy {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }
    docker version | Out-Null 2>$null
    return $LASTEXITCODE -eq 0
}

Write-Host "NOVALI guided first-run wizard"
Write-Host "Package: $packageRoot"
Write-Host ""

if (-not (Test-Path $packageRoot)) {
    throw "Missing package directory: $packageRoot"
}

if (-not (Test-DockerHealthy)) {
    Write-Warning "Docker is not healthy or not on PATH. The packaged runner may fall back to local Python if available."
}
else {
    docker image inspect $imageTag | Out-Null 2>$null
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $imageArchive) {
            Write-Host "Loading packaged Docker image archive..."
            & $loadScript
        }
        else {
            Write-Host "No image archive found. Building local Docker image from the public handoff package..."
            docker build -t $imageTag -f (Join-Path $packageRoot "Dockerfile") $packageRoot
        }
    }
}

Write-Host ""
Write-Host "Directive setup:"
Write-Host "  Use the scaffold helper when you need a first directive:"
Write-Host "  .\novali-v7_rc01-standalone\standalone_docker\generate_directive_scaffold.ps1 --output .\novali-v7_rc01-standalone\directive_inputs\my_first_directive.json --directive-id directive_my_first_run_v1 --directive-text `"Initialize NOVALI for a bounded local research and implementation planning run.`" --clarified-intent-summary `"Create reviewable local artifacts, keep all execution governed, and preserve operator-readable evidence before continuation.`""
Write-Host ""
Write-Host "Trusted-source credentials:"
Write-Host "  Do not commit secrets. Provide credentials only through your local shell or the Operator Shell when needed."
Write-Host ""
Write-Host "Starting NOVALI. The browser should open to $shellUrl"

Start-Process $shellUrl | Out-Null

Push-Location $packageRoot
try {
    & $runScript
}
finally {
    Pop-Location
}

