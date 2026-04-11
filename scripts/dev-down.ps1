[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-ProcessAlive([int]$ProcessId) {
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $repoRoot ".runtime/dev-processes.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No PID file found: $pidFile"
    return
}

$state = Get-Content -Raw $pidFile | ConvertFrom-Json
$stopped = @()

if ($null -ne $state.backend_pid -and (Test-ProcessAlive ([int]$state.backend_pid))) {
    Stop-Process -Id ([int]$state.backend_pid) -Force
    $stopped += "backend:$($state.backend_pid)"
}

if ($null -ne $state.frontend_pid -and (Test-ProcessAlive ([int]$state.frontend_pid))) {
    Stop-Process -Id ([int]$state.frontend_pid) -Force
    $stopped += "frontend:$($state.frontend_pid)"
}

Remove-Item -LiteralPath $pidFile -Force

if ($stopped.Count -eq 0) {
    Write-Host "No running tracked dev process was found."
}
else {
    Write-Host ("Stopped: " + ($stopped -join ", ")) -ForegroundColor Green
}
