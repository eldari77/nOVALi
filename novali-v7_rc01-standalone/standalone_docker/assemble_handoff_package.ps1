$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

Push-Location $packageRoot
try {
    python .\standalone_docker\assemble_handoff_package.py @args
}
finally {
    Pop-Location
}
