param(
    [ValidateSet("demo", "dev", "prod")]
    [string]$AppMode = "demo",
    [int]$BackendPort = 8000,
    [int]$BackendReadyTimeoutSeconds = 30,
    [switch]$InstallFrontend,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendScript = Join-Path $RepoRoot "scripts/dev-backend.ps1"
$FrontendScript = Join-Path $RepoRoot "scripts/dev-frontend.ps1"
$ShellExecutable = (Get-Process -Id $PID).Path
$BackendOrigin = "http://127.0.0.1:$BackendPort"

function Wait-BackendReady {
    param(
        [int]$Port,
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$Process
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $HealthUrl = "http://127.0.0.1:$Port/healthz"

    while ((Get-Date) -lt $Deadline) {
        if ($null -ne $Process) {
            $Process.Refresh()
            if ($Process.HasExited) {
                throw "Backend process exited before /healthz became ready."
            }
        }

        try {
            $Result = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
            if ($Result.status -eq "ok") {
                Write-Host "[orionstack] backend ready: $HealthUrl"
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    }

    throw "Timed out waiting for backend readiness at $HealthUrl."
}

Write-Host "[orionstack] demo mode boot"
Write-Host "[orionstack] app mode      : $AppMode"

if ($CheckOnly) {
    & $BackendScript -AppMode $AppMode -BackendHost "127.0.0.1" -Port $BackendPort -CheckOnly
    if ($InstallFrontend) {
        & $FrontendScript -Install -BackendOrigin $BackendOrigin -CheckOnly
    }
    else {
        & $FrontendScript -BackendOrigin $BackendOrigin -CheckOnly
    }
    Write-Host "[orionstack] demo check only passed."
    return
}

$BackendArgs = @(
    "-NoExit",
    "-File",
    $BackendScript,
    "-AppMode",
    $AppMode,
    "-BackendHost",
    "127.0.0.1",
    "-Port",
    "$BackendPort"
)
$BackendProcess = Start-Process -FilePath $ShellExecutable -ArgumentList $BackendArgs -PassThru

Wait-BackendReady -Port $BackendPort -TimeoutSeconds $BackendReadyTimeoutSeconds -Process $BackendProcess

$FrontendArgs = @(
    "-NoExit",
    "-File",
    $FrontendScript,
    "-BackendOrigin",
    $BackendOrigin
)
if ($InstallFrontend) {
    $FrontendArgs += "-Install"
}
Start-Process -FilePath $ShellExecutable -ArgumentList $FrontendArgs | Out-Null

Write-Host "[orionstack] frontend started in a new shell window."
