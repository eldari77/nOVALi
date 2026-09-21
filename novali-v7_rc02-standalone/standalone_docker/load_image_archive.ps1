$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
$imageArchive = Join-Path $packageRoot "image\\novali-v7-standalone.tar"
$imageManifest = Join-Path $packageRoot "image\\image_archive_manifest.json"
$readmeFirst = Join-Path $packageRoot "README_FIRST.md"
$imageTag = "novali-v7-standalone:local"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not available on PATH. Install/start Docker Desktop first, then rerun this script."
    exit 1
}

docker image inspect $imageTag | Out-Null 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "NOVALI image is already loaded: $imageTag"
    Write-Host "Package guide: $readmeFirst"
    if (Test-Path $imageManifest) {
        Write-Host "Image manifest: $imageManifest"
    }
    exit 0
}

if (-not (Test-Path $imageArchive)) {
    Write-Error "Packaged image archive not found: $imageArchive"
    Write-Host "This handoff package should normally include a prebuilt image archive."
    Write-Host "Ask the packager for a refreshed handoff package that includes image\\novali-v7-standalone.tar."
    exit 1
}

Write-Host "Loading packaged NOVALI image archive..."
Write-Host "Image archive: $imageArchive"
if (Test-Path $imageManifest) {
    Write-Host "Image manifest: $imageManifest"
}
docker load -i $imageArchive
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker load failed for $imageArchive"
    exit $LASTEXITCODE
}

Write-Host "Image load complete. Tag: $imageTag"
Write-Host "Package guide: $readmeFirst"
Write-Host "Next step: run .\\launch\\02_run_browser_operator.bat or .\\launch\\02_run_browser_operator.ps1"
Write-Host "Expected browser URL after launch: http://127.0.0.1:8787/"
