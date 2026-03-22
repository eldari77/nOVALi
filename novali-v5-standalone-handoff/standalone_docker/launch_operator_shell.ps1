$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

Push-Location $packageRoot
try {
    python -m novali_v5.operator_shell
}
finally {
    Pop-Location
}
