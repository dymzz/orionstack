$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Push-Location $RepoRoot
try {
    npx repomix --include "backend/**/*" -o repomix/repomix-backend.xml
    npx repomix --include "frontend/**/*" -o repomix/repomix-frontend.xml
    npx repomix --include "docs/**/*" -o repomix/repomix-docs.xml
    npx repomix --include "scripts/**/*" -o repomix/repomix-scripts.xml
    npx repomix --include "AGENTS.md,pyproject.toml,README.md" -o repomix/repomix-main.xml
    npx repomix --include "backend/**/*,docs/**/*,frontend/**/*,scripts/**/*,AGENTS.md,pyproject.toml,README.md" -o repomix/repomix-output.xml
}
finally {
    Pop-Location
}