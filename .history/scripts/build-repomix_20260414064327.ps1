# scripts/build-repomix.ps1
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$XmlOutput = "repomix-output.xml",
    [string]$MarkdownOutput = "repomix-output.md",
    [string]$Include = "backend/**/*,docs/**/*,README.md,pyproject.toml",
    [string]$Ignore = "frontend/**,.runtime/**,node_modules/**,dist/**,build/**,uv.lock",
    [string]$SplitOutput,
    [switch]$XmlOnly,
    [switch]$MarkdownOnly,
    [switch]$NoBanner
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title
    )
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Resolve-RepoRoot {
    param(
        [string]$InputRepoRoot
    )

    if (-not [string]::IsNullOrWhiteSpace($InputRepoRoot)) {
        return (Resolve-Path $InputRepoRoot).Path
    }

    # 默认取 scripts/ 的上一级作为仓库根目录
    $candidate = Resolve-Path (Join-Path $PSScriptRoot "..")
    return $candidate.Path
}

function Assert-GitRepo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    Push-Location $Root
    try {
        git rev-parse --is-inside-work-tree *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Target path is not inside a git repository: '$Root'"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-RepomixCommand {
    $cmd = Get-Command repomix -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw @"
repomix command not found.

Please install Repomix first, for example:
  npm install -g repomix

Then rerun this script.
"@
    }
    return $cmd.Source
}

function Build-RepomixArgs {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("xml", "markdown")]
        [string]$Style,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [Parameter(Mandatory = $true)]
        [string]$IncludePatterns,

        [Parameter(Mandatory = $true)]
        [string]$IgnorePatterns,

        [string]$SplitSize
    )

    $args = @(
        "--style", $Style,
        "--output", $OutputPath
    )

    if (-not [string]::IsNullOrWhiteSpace($IncludePatterns)) {
        $args += @("--include", $IncludePatterns)
    }

    if (-not [string]::IsNullOrWhiteSpace($IgnorePatterns)) {
        $args += @("--ignore", $IgnorePatterns)
    }

    if (-not [string]::IsNullOrWhiteSpace($SplitSize)) {
        $args += @("--split-output", $SplitSize)
    }

    return , $args
}

function Invoke-RepomixBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRootPath,

        [Parameter(Mandatory = $true)]
        [ValidateSet("xml", "markdown")]
        [string]$Style,

        [Parameter(Mandatory = $true)]
        [string]$OutputFile,

        [Parameter(Mandatory = $true)]
        [string]$IncludePatterns,

        [Parameter(Mandatory = $true)]
        [string]$IgnorePatterns,

        [string]$SplitSize
    )

    $repomixExe = Get-RepomixCommand
    $outputPath = Join-Path $RepoRootPath $OutputFile
    $args = Build-RepomixArgs `
        -Style $Style `
        -OutputPath $outputPath `
        -IncludePatterns $IncludePatterns `
        -IgnorePatterns $IgnorePatterns `
        -SplitSize $SplitSize

    Write-Section "BUILD $($Style.ToUpper())"
    Write-Host "RepoRoot : $RepoRootPath" -ForegroundColor DarkGray
    Write-Host "Output   : $outputPath" -ForegroundColor DarkGray
    Write-Host "Include  : $IncludePatterns" -ForegroundColor DarkGray
    Write-Host "Ignore   : $IgnorePatterns" -ForegroundColor DarkGray
    if (-not [string]::IsNullOrWhiteSpace($SplitSize)) {
        Write-Host "Split    : $SplitSize" -ForegroundColor DarkGray
    }

    Push-Location $RepoRootPath
    try {
        & $repomixExe @args
        if ($LASTEXITCODE -ne 0) {
            throw "repomix failed for style '$Style'."
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path $outputPath)) {
        throw "Expected output file was not created: '$outputPath'"
    }

    Write-Host "Done: $outputPath" -ForegroundColor Green
}

# -----------------------------
# Main
# -----------------------------

$resolvedRepoRoot = Resolve-RepoRoot -InputRepoRoot $RepoRoot
Assert-GitRepo -Root $resolvedRepoRoot

if (-not $NoBanner) {
    Write-Section "REPOMIX BUILD"
    Write-Host "RepoRoot        : $resolvedRepoRoot" -ForegroundColor DarkGray
    Write-Host "XML Output      : $XmlOutput" -ForegroundColor DarkGray
    Write-Host "Markdown Output : $MarkdownOutput" -ForegroundColor DarkGray
}

if ($XmlOnly -and $MarkdownOnly) {
    throw "Cannot use -XmlOnly and -MarkdownOnly at the same time."
}

if (-not $MarkdownOnly) {
    Invoke-RepomixBuild `
        -RepoRootPath $resolvedRepoRoot `
        -Style "xml" `
        -OutputFile $XmlOutput `
        -IncludePatterns $Include `
        -IgnorePatterns $Ignore `
        -SplitSize $SplitOutput
}

if (-not $XmlOnly) {
    Invoke-RepomixBuild `
        -RepoRootPath $resolvedRepoRoot `
        -Style "markdown" `
        -OutputFile $MarkdownOutput `
        -IncludePatterns $Include `
        -IgnorePatterns $Ignore `
        -SplitSize $SplitOutput
}

Write-Section "FINISHED"
Write-Host "Repomix outputs generated successfully." -ForegroundColor Green