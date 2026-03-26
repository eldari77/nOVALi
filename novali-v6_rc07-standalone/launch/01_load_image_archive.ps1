$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot
& (Join-Path $packageRoot "standalone_docker\load_image_archive.ps1") @args
