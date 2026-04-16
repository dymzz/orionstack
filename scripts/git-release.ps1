param(
    [string]$Version,
    [string]$CommitMessage,
    [string]$TagPrefix = "v",
    [string]$RemoteName = "origin",
    [switch]$SkipPush,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyprojectPath = Join-Path $RepoRoot "pyproject.toml"
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$GitExecutable = Get-Command git -ErrorAction SilentlyContinue

if ($null -eq $GitExecutable) {
    throw "git not found. Install Git first."
}

if (-not (Test-Path $PyprojectPath)) {
    throw "pyproject.toml not found: $PyprojectPath"
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $Output = & $GitExecutable.Source @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $RenderedOutput = if ($Output) { ($Output -join "`n") } else { "<no output>" }
        throw "git $($Arguments -join ' ') failed.`n$RenderedOutput"
    }

    return @($Output)
}

function Get-PyprojectVersion {
    $Content = [System.IO.File]::ReadAllText($PyprojectPath, $Utf8NoBom)
    $Match = [regex]::Match($Content, '(?m)^version\s*=\s*"([^"]+)"\s*$')
    if (-not $Match.Success) {
        throw "Could not find [project].version in pyproject.toml"
    }

    return @{
        Content = $Content
        Version = $Match.Groups[1].Value
    }
}

function Set-PyprojectVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetVersion
    )

    $State = Get-PyprojectVersion
    if ($State.Version -eq $TargetVersion) {
        return $State.Version
    }

    $UpdatedContent = [regex]::Replace(
        $State.Content,
        '(?m)^version\s*=\s*"[^"]+"\s*$',
        "version = `"$TargetVersion`"",
        1
    )
    [System.IO.File]::WriteAllText($PyprojectPath, $UpdatedContent, $Utf8NoBom)
    return $State.Version
}

function Normalize-Version {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RawVersion
    )

    $Value = $RawVersion.Trim()
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "Version cannot be empty."
    }

    if (-not [string]::IsNullOrWhiteSpace($TagPrefix) -and $Value.StartsWith($TagPrefix)) {
        $Value = $Value.Substring($TagPrefix.Length)
    }

    if ($Value -notmatch '^\d+\.\d+\.\d+([.-][0-9A-Za-z]+)*$') {
        throw "Version must look like 0.1.3 or 0.1.3-rc1"
    }

    return $Value
}

function Read-RequiredInput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    $Value = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "Required input cannot be empty."
    }

    return $Value.Trim()
}

$PyprojectState = Get-PyprojectVersion
$CurrentVersion = $PyprojectState.Version
$CurrentBranchLine = Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD") | Select-Object -First 1
$CurrentBranch = $CurrentBranchLine.ToString().Trim()

if ($CurrentBranch -eq "HEAD") {
    throw "Detached HEAD is not supported. Checkout a branch first."
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Read-RequiredInput -Prompt "Enter release version (current: $CurrentVersion)"
}

$TargetVersion = Normalize-Version -RawVersion $Version
$TagName = if ([string]::IsNullOrWhiteSpace($TagPrefix)) {
    $TargetVersion
}
else {
    "$TagPrefix$TargetVersion"
}

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    $CommitMessage = Read-RequiredInput -Prompt "Enter commit message"
}

$ExistingTagLine = Invoke-Git -Arguments @("tag", "--list", $TagName) | Select-Object -First 1
$ExistingTag = if ($null -eq $ExistingTagLine) { "" } else { $ExistingTagLine.ToString().Trim() }
if ($ExistingTag -eq $TagName) {
    throw "Tag already exists: $TagName"
}

if (-not $SkipPush) {
    Invoke-Git -Arguments @("remote", "get-url", $RemoteName) | Out-Null
}

Write-Host "[orionstack] release summary"
Write-Host "[orionstack] branch         : $CurrentBranch"
Write-Host "[orionstack] current version: $CurrentVersion"
Write-Host "[orionstack] target version : $TargetVersion"
Write-Host "[orionstack] tag            : $TagName"
Write-Host "[orionstack] commit message : $CommitMessage"
Write-Host "[orionstack] push enabled   : $(-not $SkipPush)"

if ($CheckOnly) {
    Write-Host "[orionstack] check only passed."
    return
}

$Confirmation = Read-Host "Continue with git add/commit/tag/push? (y/N)"
if ($Confirmation.Trim().ToLowerInvariant() -notin @("y", "yes")) {
    throw "Release cancelled by user."
}

$PreviousVersion = Set-PyprojectVersion -TargetVersion $TargetVersion
if ($PreviousVersion -ne $TargetVersion) {
    Write-Host "[orionstack] updated pyproject version: $PreviousVersion -> $TargetVersion"
}
else {
    Write-Host "[orionstack] pyproject version already at $TargetVersion"
}

$StatusAfterVersion = Invoke-Git -Arguments @("status", "--porcelain")
if ($StatusAfterVersion.Count -eq 0) {
    throw "No changes to commit. Update files or choose a new version first."
}

Invoke-Git -Arguments @("add", "--all") | Out-Null
Invoke-Git -Arguments @("commit", "-m", $CommitMessage) | Out-Null
Invoke-Git -Arguments @("tag", "-a", $TagName, "-m", "release $TagName") | Out-Null

if (-not $SkipPush) {
    Invoke-Git -Arguments @("push", $RemoteName, $CurrentBranch) | Out-Null
    Invoke-Git -Arguments @("push", $RemoteName, $TagName) | Out-Null
    Write-Host "[orionstack] pushed branch and tag to $RemoteName"
}
else {
    Write-Host "[orionstack] SkipPush enabled. Branch and tag remain local only."
}

Write-Host "[orionstack] release complete: $TagName"
