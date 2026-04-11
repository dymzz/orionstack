# scripts/print-main-ref.ps1
[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Ensure we are in a git repo
git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Not inside a git repository."
}

$commit = (git rev-parse HEAD).Trim()
$prUrl = "tbd"

# Try GitHub CLI first
$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    try {
        $u = (gh pr view --json url -q .url 2>$null).Trim()
        if ($u) { $prUrl = $u }
    }
    catch {}
}

# Fallback: GitLab CLI
if ($prUrl -eq "tbd") {
    $glab = Get-Command glab -ErrorAction SilentlyContinue
    if ($glab) {
        try {
            $u = (glab mr view --json web_url --jq .web_url 2>$null).Trim()
            if ($u) { $prUrl = $u }
        }
        catch {}
    }
}

if ($Json) {
    [pscustomobject]@{
        ref_main_commit = $commit
        ref_main_pr     = $prUrl
    } | ConvertTo-Json -Compress
}
else {
    Write-Output "ref_main_commit: $commit"
    Write-Output "ref_main_pr: $prUrl"
}