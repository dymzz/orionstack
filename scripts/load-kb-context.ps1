[CmdletBinding()]
param(
    [string]$KbPath = $env:ORIONSTACK_KB_PATH,
    [string]$Query,
    [switch]$AllContext,
    [switch]$DesignsOnly,
    [switch]$NoRead,
    [switch]$PersistUser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 80) -ForegroundColor DarkGray
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor DarkGray
}

# Auto-detect KB path if not provided
if ([string]::IsNullOrWhiteSpace($KbPath)) {
    $candidate = Join-Path (Split-Path $PSScriptRoot -Parent) "orionstack-kb"
    if (Test-Path $candidate) { $KbPath = $candidate }
}

if ([string]::IsNullOrWhiteSpace($KbPath)) {
    throw "KB path not found. Pass -KbPath or set ORIONSTACK_KB_PATH."
}

$KbPath = (Resolve-Path $KbPath).Path
if (-not (Test-Path (Join-Path $KbPath "context"))) {
    throw "Invalid KB path: '$KbPath' (missing context/)."
}

# Set env for current session
$env:ORIONSTACK_KB_PATH = $KbPath
if ($PersistUser) {
    [Environment]::SetEnvironmentVariable("ORIONSTACK_KB_PATH", $KbPath, "User")
}

Write-Host "ORIONSTACK_KB_PATH = $KbPath" -ForegroundColor Green

$defaultContextFiles = @(
    "context/project_index.md",
    "context/current_phase.md",
    "context/frozen_contracts.md",
    "context/ai_entry.md"
)

if (-not $NoRead) {
    $filesToRead = if ($AllContext) {
        Get-ChildItem -Path (Join-Path $KbPath "context") -Filter *.md -File |
        ForEach-Object { "context/$($_.Name)" }
    }
    else {
        $defaultContextFiles
    }

    foreach ($rel in $filesToRead) {
        $full = Join-Path $KbPath $rel
        if (Test-Path $full) {
            Write-Section "READ: $rel"
            Get-Content -Raw $full
        }
        else {
            Write-Host "Skip missing: $rel" -ForegroundColor Yellow
        }
    }
}

if (-not [string]::IsNullOrWhiteSpace($Query)) {
    $searchPath = if ($DesignsOnly) {
        Join-Path $KbPath "docs/designs"
    }
    else {
        Join-Path $KbPath "docs"
    }

    Write-Section "SEARCH: '$Query' in $searchPath"

    $rg = Get-Command rg -ErrorAction SilentlyContinue
    if ($null -ne $rg) {
        & rg -n --color never --glob "*.md" $Query $searchPath
    }
    else {
        Get-ChildItem -Path $searchPath -Recurse -File -Filter *.md |
        Select-String -Pattern $Query -CaseSensitive:$false |
        ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    }
}
