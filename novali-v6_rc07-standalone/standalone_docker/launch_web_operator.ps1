$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptRoot

Push-Location $packageRoot
try {
    python -m novali_v5.web_operator --host 127.0.0.1 --port 8787 @args
}
finally {
    Pop-Location
}
