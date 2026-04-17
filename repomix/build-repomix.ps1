$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

$IgnorePatterns = "backend/tests/**,backend/app/storage/seed/**,frontend/dist/**"

Push-Location $RepoRoot
try {
    npx repomix --include "backend/**/*" --ignore $IgnorePatterns -o repomix/repomix-backend.xml
    npx repomix --include "frontend/**/*" --ignore $IgnorePatterns -o repomix/repomix-frontend.xml
    npx repomix --include "docs/**/*" --ignore $IgnorePatterns -o repomix/repomix-docs.xml
    npx repomix --include "scripts/**/*" --ignore $IgnorePatterns -o repomix/repomix-scripts.xml
    npx repomix --include "AGENTS.md,pyproject.toml,README.md" --ignore $IgnorePatterns -o repomix/repomix-main.xml
    npx repomix --include "backend/**/*,docs/**/*,frontend/**/*,scripts/**/*,AGENTS.md,pyproject.toml,README.md" --ignore $IgnorePatterns -o repomix/repomix-output.xml
}
finally {
    Pop-Location
}