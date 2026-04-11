[CmdletBinding()]
param(
    [string]$KbPath = $env:ORIONSTACK_KB_PATH,
    [string]$Query,
    [string]$Since = "HEAD~1",
    [string]$NewDesign,
    [string]$Version,
    [string]$CommitSubject,
    [string]$RefKb,
    [string]$UpdatedKb,
    [string]$KbCommitSubject,
    [string]$KbUpdated,
    [string]$RefMain,
    [switch]$AllContext,
    [switch]$DesignsOnly,
    [switch]$NoRead,
    [switch]$PersistUser,
    [switch]$RunRepomix,
    [switch]$Interactive,
    [switch]$CommitChanges,
    [switch]$StageAll
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 80) -ForegroundColor DarkGray
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor DarkGray
}

function Read-OptionalValue([string]$Prompt, [string]$Default = "") {
    if ([string]::IsNullOrWhiteSpace($Default)) {
        return (Read-Host $Prompt).Trim()
    }

    $value = (Read-Host "$Prompt [$Default]").Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }

    return $value
}

function Read-RequiredValue([string]$Prompt, [string]$Default = "") {
    while ($true) {
        $value = Read-OptionalValue -Prompt $Prompt -Default $Default
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }

        Write-Host "This value is required." -ForegroundColor Yellow
    }
}

function Read-YesNo([string]$Prompt, [bool]$Default = $true) {
    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }

    while ($true) {
        $value = (Read-Host "$Prompt $suffix").Trim().ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($value)) {
            return $Default
        }

        if ($value -in @("y", "yes")) {
            return $true
        }

        if ($value -in @("n", "no")) {
            return $false
        }

        Write-Host "Please answer y or n." -ForegroundColor Yellow
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Resolve-KbPath([string]$CandidatePath) {
    if (-not [string]::IsNullOrWhiteSpace($CandidatePath)) {
        return (Resolve-Path $CandidatePath).Path
    }

    $workspaceRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $workspaceCandidate = Join-Path $workspaceRoot "orionstack-kb"
    if (Test-Path $workspaceCandidate) {
        return (Resolve-Path $workspaceCandidate).Path
    }

    throw "KB path not found. Pass -KbPath or set ORIONSTACK_KB_PATH."
}

function Get-CommandOutput([string]$FilePath, [string[]]$ArgumentList) {
    try {
        $output = & $FilePath @ArgumentList 2>$null
        if ($LASTEXITCODE -eq 0 -and $null -ne $output) {
            return ($output | Out-String).Trim()
        }
    }
    catch {}

    return $null
}

function Get-MainRepoRoot() {
    $repoRoot = Get-CommandOutput "git" @("rev-parse", "--show-toplevel")
    if ([string]::IsNullOrWhiteSpace($repoRoot)) {
        throw "Not inside a git repository."
    }

    return $repoRoot
}

function Get-PyProjectPath([string]$RepoRoot) {
    $path = Join-Path $RepoRoot "pyproject.toml"
    if (-not (Test-Path $path)) {
        throw "pyproject.toml not found at $path"
    }

    return $path
}

function Get-CurrentVersion([string]$RepoRoot) {
    $pyprojectPath = Get-PyProjectPath $RepoRoot
    $content = Get-Content -Raw $pyprojectPath
    $match = [regex]::Match($content, '(?m)^version\s*=\s*["'']([^"'']+)["'']\s*$')
    if (-not $match.Success) {
        throw "Could not find version in $pyprojectPath"
    }

    return $match.Groups[1].Value
}

function Set-ProjectVersion([string]$RepoRoot, [string]$NewVersion) {
    $pyprojectPath = Get-PyProjectPath $RepoRoot
    $content = Get-Content -Raw $pyprojectPath
    $updated = [regex]::Replace($content, '(?m)^version\s*=\s*["''][^"'']+["'']\s*$', "version = ""$NewVersion""", 1)

    if ($updated -eq $content) {
        throw "Version update did not change pyproject.toml"
    }

    Write-Utf8NoBom -Path $pyprojectPath -Content $updated
    return $pyprojectPath
}

function Get-MainRefs() {
    $commit = Get-CommandOutput "git" @("rev-parse", "HEAD")
    $branch = Get-CommandOutput "git" @("branch", "--show-current")
    $prUrl = "tbd"

    if ([string]::IsNullOrWhiteSpace($commit)) {
        $commit = "tbd"
    }

    if ([string]::IsNullOrWhiteSpace($branch)) {
        $branch = "unknown"
    }

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        $ghUrl = Get-CommandOutput "gh" @("pr", "view", "--json", "url", "-q", ".url")
        if (-not [string]::IsNullOrWhiteSpace($ghUrl)) {
            $prUrl = $ghUrl
        }
    }

    if ($prUrl -eq "tbd" -and (Get-Command glab -ErrorAction SilentlyContinue)) {
        $glabUrl = Get-CommandOutput "glab" @("mr", "view", "--json", "web_url", "--jq", ".web_url")
        if (-not [string]::IsNullOrWhiteSpace($glabUrl)) {
            $prUrl = $glabUrl
        }
    }

    [pscustomobject]@{
        Branch = $branch
        Commit = $commit
        PrUrl  = $prUrl
    }
}

function Get-ChangedFiles([string]$Ref) {
    $files = New-Object System.Collections.Generic.HashSet[string]
    $headExists = -not [string]::IsNullOrWhiteSpace((Get-CommandOutput "git" @("rev-parse", "HEAD")))

    $refExists = $false
    if (-not [string]::IsNullOrWhiteSpace($Ref)) {
        $refExists = -not [string]::IsNullOrWhiteSpace((Get-CommandOutput "git" @("rev-parse", "--verify", $Ref)))
    }

    if ($refExists -and $headExists) {
        $sinceFiles = & git diff --name-only $Ref HEAD 2>$null
        foreach ($file in $sinceFiles) {
            if (-not [string]::IsNullOrWhiteSpace($file)) {
                $null = $files.Add($file.Trim())
            }
        }
    }

    $workingTreeFiles = @(
        (& git diff --name-only 2>$null),
        (& git diff --cached --name-only 2>$null),
        (& git ls-files --others --exclude-standard 2>$null)
    )

    foreach ($group in $workingTreeFiles) {
        foreach ($file in $group) {
            if (-not [string]::IsNullOrWhiteSpace($file)) {
                $null = $files.Add($file.Trim())
            }
        }
    }

    return [pscustomobject]@{
        RefExists = $refExists
        Files     = @($files | Sort-Object)
    }
}

function Get-KbSuggestions([string[]]$ChangedFiles) {
    $suggestions = New-Object System.Collections.Generic.HashSet[string]

    $alwaysCheck = @(
        "context/project_index.md",
        "context/current_phase.md",
        "context/frozen_contracts.md",
        "docs/engineering/repo_map.md"
    )

    foreach ($item in $alwaysCheck) {
        $null = $suggestions.Add($item)
    }

    foreach ($file in $ChangedFiles) {
        if ($file -match "^backend/app/api/" -or
            $file -match "^frontend/src/services/" -or
            $file -match "^docs/api/") {
            $null = $suggestions.Add("docs/api/api_contract_draft.md")
            $null = $suggestions.Add("docs/api/error_model.md")
        }

        if ($file -match "^backend/app/workflows/" -or
            $file -match "^backend/app/services/qa_service\.py$" -or
            $file -match "^backend/app/api/routes/qa\.py$") {
            $null = $suggestions.Add("docs/workflows/knowledge_assistant_flow.md")
            $null = $suggestions.Add("docs/workflows/workflow_state_objects.md")
            $null = $suggestions.Add("docs/workflows/workflow_error_paths.md")
        }

        if ($file -match "^backend/app/knowledge/" -or
            $file -match "^backend/app/core/" -or
            $file -match "^backend/app/integrations/" -or
            $file -match "^docs/architecture/") {
            $null = $suggestions.Add("docs/architecture/module_boundaries.md")
            $null = $suggestions.Add("docs/architecture/system_layers.md")
        }

        if ($file -match "^docs/product/" -or
            $file -match "^frontend/src/pages/" -or
            $file -match "^backend/app/api/routes/documents\.py$") {
            $null = $suggestions.Add("docs/product/mvp_scope.md")
        }
    }

    return @($suggestions | Sort-Object)
}

function Build-CommitMessage(
    [string]$Subject,
    [string]$RefKbValue,
    [string]$UpdatedKbValue,
    [string]$VersionValue
) {
    $lines = New-Object System.Collections.Generic.List[string]
    $null = $lines.Add($Subject.Trim())

    $body = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($VersionValue)) {
        $null = $body.Add("version: $VersionValue")
    }

    if (-not [string]::IsNullOrWhiteSpace($RefKbValue)) {
        $null = $body.Add("ref-kb: $RefKbValue")
    }

    if (-not [string]::IsNullOrWhiteSpace($UpdatedKbValue)) {
        $null = $body.Add("updated: $UpdatedKbValue")
    }

    if ($body.Count -gt 0) {
        $null = $lines.Add("")
        foreach ($line in $body) {
            $null = $lines.Add($line)
        }
    }

    return ($lines -join [Environment]::NewLine)
}

function Build-KbCommitMessage(
    [string]$Subject,
    [string]$RefMainValue,
    [string]$RefMainPrValue,
    [string]$UpdatedValue
) {
    $lines = New-Object System.Collections.Generic.List[string]
    $null = $lines.Add($Subject.Trim())

    $body = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($RefMainValue)) {
        $null = $body.Add("ref-main: $RefMainValue")
    }

    if (-not [string]::IsNullOrWhiteSpace($RefMainPrValue) -and $RefMainPrValue -ne "tbd") {
        $null = $body.Add("ref-main-pr: $RefMainPrValue")
    }

    if (-not [string]::IsNullOrWhiteSpace($UpdatedValue)) {
        $null = $body.Add("updated: $UpdatedValue")
    }

    if ($body.Count -gt 0) {
        $null = $lines.Add("")
        foreach ($line in $body) {
            $null = $lines.Add($line)
        }
    }

    return ($lines -join [Environment]::NewLine)
}

function New-DesignDocFromTemplate(
    [string]$TemplatePath,
    [string]$TargetDirectory,
    [string]$DesignName,
    [string]$Commit,
    [string]$PrUrl
) {
    $slug = ($DesignName.ToLowerInvariant() -replace "[^a-z0-9]+", "_").Trim("_")
    if ([string]::IsNullOrWhiteSpace($slug)) {
        throw "NewDesign must contain letters or numbers."
    }

    if ($slug.StartsWith("design_")) {
        $baseName = $slug
    }
    else {
        $baseName = "design_$slug"
    }

    $todayCompact = Get-Date -Format "yyyyMMdd"
    $today = Get-Date -Format "yyyy-MM-dd"
    $fileName = "$baseName`_v$todayCompact.md"
    $targetPath = Join-Path $TargetDirectory $fileName

    if (Test-Path $targetPath) {
        throw "Design doc already exists: $targetPath"
    }

    $template = Get-Content -Raw $TemplatePath
    $content = $template.Replace("<Design Title>", $DesignName)
    $content = $content.Replace("<name>", $env:USERNAME)
    $content = $content.Replace("<YYYY-MM-DD>", $today)
    $content = $content.Replace("<pr-link-or-id>", $PrUrl)
    $content = $content.Replace("<commit-sha>", $Commit)

    Write-Utf8NoBom -Path $targetPath -Content $content
    return $targetPath
}

function Invoke-Repomix([string]$SourcePath, [string]$OutputPath) {
    $repomix = Get-Command repomix -ErrorAction SilentlyContinue
    if ($null -eq $repomix) {
        throw "repomix command not found. Install it first or rerun without -RunRepomix."
    }

    $previousPythonUtf8 = $env:PYTHONUTF8
    $previousPythonIoEncoding = $env:PYTHONIOENCODING

    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    try {
        & $repomix.Source $SourcePath --output $OutputPath
        if ($LASTEXITCODE -ne 0) {
            throw "repomix failed for $SourcePath. Check local permissions and rerun from a normal terminal."
        }
    }
    finally {
        $env:PYTHONUTF8 = $previousPythonUtf8
        $env:PYTHONIOENCODING = $previousPythonIoEncoding
    }
}

function Invoke-GitCommit(
    [string]$RepoRoot,
    [string]$Message,
    [bool]$ShouldStageAll
) {
    if ($ShouldStageAll) {
        & git -C $RepoRoot add -A
        if ($LASTEXITCODE -ne 0) {
            throw "git add -A failed."
        }
    }

    $stagedFiles = & git -C $RepoRoot diff --cached --name-only
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect staged files."
    }

    if ($null -eq $stagedFiles -or @($stagedFiles).Count -eq 0) {
        throw "No staged changes to commit."
    }

    $tempMessagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("orionstack-commit-" + [guid]::NewGuid().ToString() + ".txt")
    try {
        Write-Utf8NoBom -Path $tempMessagePath -Content $Message
        & git -C $RepoRoot commit -F $tempMessagePath
        if ($LASTEXITCODE -ne 0) {
            throw "git commit failed."
        }
    }
    finally {
        if (Test-Path $tempMessagePath) {
            Remove-Item -LiteralPath $tempMessagePath -Force
        }
    }
}

$mainRepoRoot = Get-MainRepoRoot
$KbPath = Resolve-KbPath $KbPath

if (-not (Test-Path (Join-Path $KbPath "context"))) {
    throw "Invalid KB path: '$KbPath' (missing context/)."
}

$designsPath = Join-Path $KbPath "docs/designs"
$repomixMainPath = Join-Path $KbPath "repomix/main_repo/repomix-output.xml"
$repomixFrontendPath = Join-Path $KbPath "repomix/frontend_repo/repomix-output.xml"
$templatePath = Join-Path $KbPath "templates/design_doc_template.md"
$currentVersion = Get-CurrentVersion $mainRepoRoot
$versionUpdatedPath = $null
$mainCommitMessage = $null
$kbCommitMessage = $null
$confirmCommit = $false
$generateKbDraft = $false

$env:ORIONSTACK_KB_PATH = $KbPath
if ($PersistUser) {
    [Environment]::SetEnvironmentVariable("ORIONSTACK_KB_PATH", $KbPath, "User")
}

if ($Interactive) {
    Write-Section "INTERACTIVE INPUT"
    Write-Host "current_version: $currentVersion"

    $Version = Read-OptionalValue -Prompt "New version (leave blank to keep current)" -Default $Version

    if (Read-YesNo -Prompt "Create a git commit in this run?" -Default ($CommitChanges.IsPresent -or -not [string]::IsNullOrWhiteSpace($CommitSubject))) {
        $CommitChanges = $true
        $CommitSubject = Read-RequiredValue -Prompt "Commit subject" -Default $CommitSubject
        $RefKb = Read-OptionalValue -Prompt "ref-kb" -Default $RefKb
        $UpdatedKb = Read-OptionalValue -Prompt "updated" -Default $UpdatedKb
        $StageAll = Read-YesNo -Prompt "Run git add -A before commit?" -Default ($StageAll.IsPresent -or $true)
        $confirmCommit = Read-YesNo -Prompt "Execute git commit after showing the draft?" -Default $true
    }

    if (Read-YesNo -Prompt "Generate KB commit message draft?" -Default ($true -or -not [string]::IsNullOrWhiteSpace($KbCommitSubject))) {
        $generateKbDraft = $true
        $KbCommitSubject = Read-RequiredValue -Prompt "KB commit subject" -Default $KbCommitSubject
        $KbUpdated = Read-OptionalValue -Prompt "KB updated" -Default $KbUpdated
        $RefMain = Read-OptionalValue -Prompt "ref-main override (leave blank to use latest main commit)" -Default $RefMain
    }
}

if (-not [string]::IsNullOrWhiteSpace($Version) -and $Version -ne $currentVersion) {
    $versionUpdatedPath = Set-ProjectVersion -RepoRoot $mainRepoRoot -NewVersion $Version
    $currentVersion = $Version
}

if ($CommitChanges -and [string]::IsNullOrWhiteSpace($CommitSubject)) {
    throw "CommitSubject is required when -CommitChanges is used."
}

if (-not [string]::IsNullOrWhiteSpace($CommitSubject)) {
    $mainCommitMessage = Build-CommitMessage `
        -Subject $CommitSubject `
        -RefKbValue $RefKb `
        -UpdatedKbValue $UpdatedKb `
        -VersionValue $(if ($versionUpdatedPath) { $currentVersion } else { "" })
}

if (-not [string]::IsNullOrWhiteSpace($KbCommitSubject)) {
    $generateKbDraft = $true
}

$mainRefs = Get-MainRefs
$changes = Get-ChangedFiles $Since
$suggestions = Get-KbSuggestions $changes.Files

if (-not $NoRead -or -not [string]::IsNullOrWhiteSpace($Query)) {
    & (Join-Path $PSScriptRoot "load-kb-context.ps1") `
        -KbPath $KbPath `
        -Query $Query `
        -AllContext:$AllContext `
        -DesignsOnly:$DesignsOnly `
        -NoRead:$NoRead `
        -PersistUser:$PersistUser
}
else {
    Write-Host "ORIONSTACK_KB_PATH = $KbPath" -ForegroundColor Green
}

$newDesignPath = $null
if (-not [string]::IsNullOrWhiteSpace($NewDesign)) {
    $newDesignPath = New-DesignDocFromTemplate `
        -TemplatePath $templatePath `
        -TargetDirectory $designsPath `
        -DesignName $NewDesign `
        -Commit $mainRefs.Commit `
        -PrUrl $mainRefs.PrUrl
}

if ($RunRepomix) {
    Invoke-Repomix -SourcePath $mainRepoRoot -OutputPath $repomixMainPath

    $frontendPath = Join-Path $mainRepoRoot "frontend"
    if (Test-Path $frontendPath) {
        Invoke-Repomix -SourcePath $frontendPath -OutputPath $repomixFrontendPath
    }
}

Write-Section "KB SYNC START"
Write-Host "main_repo_root: $mainRepoRoot"
Write-Host "kb_path: $KbPath"
Write-Host "design_docs_path: $designsPath"
Write-Host "repomix_main_output: $repomixMainPath"
Write-Host "repomix_frontend_output: $repomixFrontendPath"

Write-Section "MAIN REFS"
Write-Host "branch: $($mainRefs.Branch)"
Write-Host "ref_main_commit: $($mainRefs.Commit)"
Write-Host "ref_main_pr: $($mainRefs.PrUrl)"
Write-Host "project_version: $currentVersion"

if ($versionUpdatedPath) {
    Write-Host "version_updated_file: $versionUpdatedPath"
}

Write-Section "CHANGED FILES"
if ($changes.RefExists) {
    Write-Host "since_ref: $Since"
}
else {
    Write-Host "since_ref: skipped ($Since not found)"
}

if ($changes.Files.Count -eq 0) {
    Write-Host "No changed files detected."
}
else {
    foreach ($file in $changes.Files) {
        Write-Host "- $file"
    }
}

Write-Section "KB CHECKLIST"
foreach ($item in $suggestions) {
    Write-Host "- $item"
}
Write-Host "- docs/designs/ (add or update a design doc when the change needs stable implementation context)"
Write-Host "- repomix/main_repo/repomix-output.xml (refresh when repo structure or large code context changes)"
Write-Host "- repomix/frontend_repo/repomix-output.xml (refresh when frontend context changes)"

if ($newDesignPath) {
    Write-Section "NEW DESIGN DOC"
    Write-Host "created: $newDesignPath"
}

if ($RunRepomix) {
    Write-Section "REPOMIX"
    Write-Host "repomix outputs refreshed."
}

if ($mainCommitMessage) {
    Write-Section "MAIN COMMIT MESSAGE DRAFT"
    Write-Host $mainCommitMessage
}

if ($CommitChanges) {
    if (-not $Interactive) {
        $confirmCommit = $true
    }

    if ($confirmCommit) {
        Invoke-GitCommit -RepoRoot $mainRepoRoot -Message $mainCommitMessage -ShouldStageAll ([bool]$StageAll)
        $mainRefs = Get-MainRefs

        Write-Section "POST COMMIT REFS"
        Write-Host "branch: $($mainRefs.Branch)"
        Write-Host "ref_main_commit: $($mainRefs.Commit)"
        Write-Host "ref_main_pr: $($mainRefs.PrUrl)"
    }
    else {
        Write-Section "COMMIT"
        Write-Host "Commit skipped after draft preview."
    }
}

if ($generateKbDraft) {
    $kbRefMain = $RefMain
    if ([string]::IsNullOrWhiteSpace($kbRefMain)) {
        if ($mainRefs.Commit -ne "tbd") {
            $kbRefMain = $mainRefs.Commit
        }
        elseif ($mainRefs.PrUrl -ne "tbd") {
            $kbRefMain = $mainRefs.PrUrl
        }
        else {
            $kbRefMain = "tbd"
        }
    }

    $kbCommitMessage = Build-KbCommitMessage `
        -Subject $KbCommitSubject `
        -RefMainValue $kbRefMain `
        -RefMainPrValue $mainRefs.PrUrl `
        -UpdatedValue $KbUpdated

    Write-Section "KB COMMIT MESSAGE DRAFT"
    Write-Host $kbCommitMessage
}
