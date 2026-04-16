param(
    [ValidateSet("demo", "dev", "prod")]
    [string]$AppMode = "dev",
    [string]$BackendHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $RepoRoot ".venv\\Scripts\\python.exe"

if (Test-Path $VenvPython) {
    $PythonCommand = $VenvPython
}
else {
    $PythonExecutable = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonExecutable) {
        throw "Python not found. Activate the project environment or install Python first."
    }
    $PythonCommand = $PythonExecutable.Source
}

Write-Host "[orionstack] backend mode: $AppMode"
Write-Host "[orionstack] backend url : http://${BackendHost}:$Port"
Write-Host "[orionstack] python      : $PythonCommand"

if ($CheckOnly) {
    Write-Host "[orionstack] backend check only passed."
    return
}

$env:ORIONSTACK_APP_MODE = $AppMode
$env:ORIONSTACK_HOST = $BackendHost
$env:ORIONSTACK_PORT = "$Port"

Push-Location $BackendRoot
try {
    & $PythonCommand -m uvicorn main:app --reload --host $BackendHost --port $Port
}
finally {
    Pop-Location
}
