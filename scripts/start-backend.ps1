param(
    [string]$AppMode = "prod",
    [string]$BackendHost = "127.0.0.1",
    [int]$Port = 8000,
    [int]$Workers = 1,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

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

Write-Host "[orionstack] start-backend mode: $AppMode"
Write-Host "[orionstack] start-backend host : ${BackendHost}:$Port"
Write-Host "[orionstack] start-backend workers: $Workers"
Write-Host "[orionstack] start-backend python: $PythonCommand"

if ($CheckOnly) {
    Write-Host "[orionstack] start-backend check only passed."
    return
}

$env:ORIONSTACK_APP_MODE = $AppMode
$env:ORIONSTACK_HOST = $BackendHost
$env:ORIONSTACK_PORT = "$Port"

Push-Location $BackendRoot
try {
    & $PythonCommand -m uvicorn main:app --host $BackendHost --port $Port --workers $Workers
}
finally {
    Pop-Location
}