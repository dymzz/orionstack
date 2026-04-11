[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$Restart,
    [switch]$NoReload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot() {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Test-ProcessAlive([int]$ProcessId) {
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Stop-TrackedProcess([int]$ProcessId) {
    if (Test-ProcessAlive $ProcessId) {
        Stop-Process -Id $ProcessId -Force
    }
}

function Wait-HttpReady([string]$Url, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing
            return $true
        }
        catch {
            Start-Sleep -Milliseconds 600
        }
    }

    return $false
}

function Escape-SingleQuote([string]$Value) {
    return $Value -replace "'", "''"
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$dbConfigPath = Join-Path $backendDir "config/database.local.yaml"
$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
$uvCacheDir = Join-Path $repoRoot ".uv-cache"
$runtimeDir = Join-Path $repoRoot ".runtime"
$pidFile = Join-Path $runtimeDir "dev-processes.json"
$backendLog = Join-Path $runtimeDir "backend.log"
$backendErr = Join-Path $runtimeDir "backend.err.log"
$frontendLog = Join-Path $runtimeDir "frontend.log"
$frontendErr = Join-Path $runtimeDir "frontend.err.log"

if (-not (Test-Path $backendDir)) {
    throw "backend directory not found: $backendDir"
}

if (-not (Test-Path $frontendDir)) {
    throw "frontend directory not found: $frontendDir"
}

if (-not (Test-Path $dbConfigPath)) {
    throw "database config not found: $dbConfigPath"
}

$null = New-Item -ItemType Directory -Path $runtimeDir -Force
$null = New-Item -ItemType Directory -Path $uvCacheDir -Force

if (Test-Path $pidFile) {
    $existing = Get-Content -Raw $pidFile | ConvertFrom-Json
    $backendAlive = $false
    $frontendAlive = $false

    if ($null -ne $existing.backend_pid) {
        $backendAlive = Test-ProcessAlive ([int]$existing.backend_pid)
    }

    if ($null -ne $existing.frontend_pid) {
        $frontendAlive = Test-ProcessAlive ([int]$existing.frontend_pid)
    }

    if ($backendAlive -or $frontendAlive) {
        if (-not $Restart) {
            throw "Dev processes are already running. Use -Restart to relaunch."
        }

        if ($backendAlive) {
            Stop-TrackedProcess ([int]$existing.backend_pid)
        }
        if ($frontendAlive) {
            Stop-TrackedProcess ([int]$existing.frontend_pid)
        }
    }
}

$shellExe = (Get-Process -Id $PID).Path

$escapedBackendDir = Escape-SingleQuote $backendDir
$escapedFrontendDir = Escape-SingleQuote $frontendDir
$escapedDbConfig = Escape-SingleQuote $dbConfigPath
$escapedUvCache = Escape-SingleQuote $uvCacheDir
$escapedVenvPython = Escape-SingleQuote $venvPython

if (Test-Path $venvPython) {
    $reloadFlag = if ($NoReload) { "" } else { " --reload" }
    $backendCommand = @(
        "`$env:ORIONSTACK_DB_CONFIG = '$escapedDbConfig'"
        "Set-Location '$escapedBackendDir'"
        "& '$escapedVenvPython' -m uvicorn main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
    ) -join "; "
}
else {
    $reloadFlag = if ($NoReload) { "" } else { " --reload" }
    $backendCommand = @(
        "`$env:ORIONSTACK_DB_CONFIG = '$escapedDbConfig'"
        "`$env:UV_CACHE_DIR = '$escapedUvCache'"
        "Set-Location '$escapedBackendDir'"
        "uv run uvicorn main:app$reloadFlag --host 127.0.0.1 --port $BackendPort"
    ) -join "; "
}

$frontendCommand = @(
    "Set-Location '$escapedFrontendDir'"
    "npm run dev -- --host 127.0.0.1 --port $FrontendPort"
) -join "; "

$backendProc = Start-Process `
    -FilePath $shellExe `
    -ArgumentList @("-NoLogo", "-NoProfile", "-Command", $backendCommand) `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErr `
    -PassThru

$frontendProc = Start-Process `
    -FilePath $shellExe `
    -ArgumentList @("-NoLogo", "-NoProfile", "-Command", $frontendCommand) `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErr `
    -PassThru

$state = [pscustomobject]@{
    backend_pid     = $backendProc.Id
    frontend_pid    = $frontendProc.Id
    backend_port    = $BackendPort
    frontend_port   = $FrontendPort
    started_at      = (Get-Date).ToString("s")
    backend_log     = $backendLog
    backend_err_log = $backendErr
    frontend_log    = $frontendLog
    frontend_err_log= $frontendErr
}

$state | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

$backendReady = Wait-HttpReady -Url "http://127.0.0.1:$BackendPort/healthz" -TimeoutSeconds 40
$frontendReady = Wait-HttpReady -Url "http://127.0.0.1:$FrontendPort/" -TimeoutSeconds 40

Write-Host ""
Write-Host "Dev services started." -ForegroundColor Green
Write-Host "Backend PID : $($backendProc.Id)"
Write-Host "Frontend PID: $($frontendProc.Id)"
Write-Host "Backend URL : http://127.0.0.1:$BackendPort/healthz"
Write-Host "Frontend URL: http://127.0.0.1:$FrontendPort/"
Write-Host "PID file    : $pidFile"

if (-not $backendReady) {
    Write-Warning "Backend health check did not pass yet. Check $backendErr"
}

if (-not $frontendReady) {
    Write-Warning "Frontend URL did not respond yet. Check $frontendErr"
}
