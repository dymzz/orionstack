param(
    [switch]$Install,
    [string]$BackendOrigin = "http://127.0.0.1:8000",
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $RepoRoot "frontend"
$NodeModulesPath = Join-Path $FrontendRoot "node_modules"
$LockFilePath = Join-Path $FrontendRoot "package-lock.json"
$NpmExecutable = Get-Command npm -ErrorAction SilentlyContinue

if ($null -eq $NpmExecutable) {
    throw "npm not found. Install Node.js first."
}

$ShouldInstallDeps = $Install -or -not (Test-Path $NodeModulesPath)
$InstallMode = if ($Install) {
    "npm install"
}
elseif (-not (Test-Path $NodeModulesPath) -and (Test-Path $LockFilePath)) {
    "npm ci"
}
elseif (-not (Test-Path $NodeModulesPath)) {
    "npm install"
}
else {
    "skip"
}

Write-Host "[orionstack] frontend root: $FrontendRoot"
Write-Host "[orionstack] dependency step: $InstallMode"
Write-Host "[orionstack] backend origin : $BackendOrigin"

if ($CheckOnly) {
    Write-Host "[orionstack] frontend check only passed."
    return
}

Push-Location $FrontendRoot
try {
    $env:ORIONSTACK_BACKEND_ORIGIN = $BackendOrigin

    if ($ShouldInstallDeps) {
        if ($InstallMode -eq "npm ci") {
            & $NpmExecutable.Source ci
        }
        else {
            & $NpmExecutable.Source install
        }
    }
    else {
        Write-Host "[orionstack] node_modules already present, skipping dependency install."
    }

    & $NpmExecutable.Source run dev
}
finally {
    Pop-Location
}
