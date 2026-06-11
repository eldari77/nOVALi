$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

Push-Location $packageRoot
try {
    python .\standalone_docker\export_standalone_image_archive.py @args
}
finally {
    Pop-Location
}
