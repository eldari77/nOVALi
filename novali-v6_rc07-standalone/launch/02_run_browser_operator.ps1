$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
& (Join-Path $packageRoot "standalone_docker\run_web_operator_container.ps1") @args
