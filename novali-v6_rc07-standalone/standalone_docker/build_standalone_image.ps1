$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

Push-Location $packageRoot
try {
    docker build -t novali-v6-standalone:local -f Dockerfile .
}
finally {
    Pop-Location
}
