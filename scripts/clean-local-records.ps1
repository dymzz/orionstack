[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$ChatOnly,
    [switch]$FeedbackOnly,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$Targets = @(
    @{
        Name = "chat records"
        Path = Join-Path $RepoRoot "backend/app/storage/chat_records/chat_records.jsonl"
    },
    @{
        Name = "feedback records"
        Path = Join-Path $RepoRoot "backend/app/storage/feedback/feedback_records.jsonl"
    }
)

if ($ChatOnly -and -not $FeedbackOnly) {
    $Targets = $Targets | Where-Object { $_.Name -eq "chat records" }
}
elseif ($FeedbackOnly -and -not $ChatOnly) {
    $Targets = $Targets | Where-Object { $_.Name -eq "feedback records" }
}

function Get-RecordSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return [pscustomobject]@{
            Exists = $false
            Lines = 0
            SizeBytes = 0
        }
    }

    $Item = Get-Item $Path
    $Lines = (Get-Content $Path -Encoding UTF8 | Measure-Object -Line).Lines
    return [pscustomobject]@{
        Exists = $true
        Lines = $Lines
        SizeBytes = $Item.Length
    }
}

Write-Host "[orionstack] local record maintenance"

foreach ($Target in $Targets) {
    $Summary = Get-RecordSummary -Path $Target.Path
    if ($Summary.Exists) {
        Write-Host "[orionstack] $($Target.Name): $($Target.Path)"
        Write-Host "[orionstack]   lines=$($Summary.Lines) size_bytes=$($Summary.SizeBytes)"
    }
    else {
        Write-Host "[orionstack] $($Target.Name): missing ($($Target.Path))"
    }
}

if ($CheckOnly) {
    Write-Host "[orionstack] check only passed."
    return
}

$ExistingTargets = @($Targets | Where-Object { (Get-RecordSummary -Path $_.Path).Exists })
if ($ExistingTargets.Count -eq 0) {
    Write-Host "[orionstack] no local record files to clean."
    return
}

foreach ($Target in $ExistingTargets) {
    if ($PSCmdlet.ShouldProcess($Target.Path, "Remove local record file")) {
        Remove-Item $Target.Path -Force
        Write-Host "[orionstack] removed: $($Target.Path)"
    }
}

Write-Host "[orionstack] local record cleanup complete."
