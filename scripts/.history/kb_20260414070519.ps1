[CmdletBinding()]
param(
    [string]$KbPath,
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
    [switch]$RunDocsRepomix,
    [switch]$Interactive,
    [switch]$CommitChanges,
    [switch]$StageAll
)

& (Join-Path $PSScriptRoot "start-kb-sync.ps1") `
    -Easy `
    -KbPath $KbPath `
    -Query $Query `
    -Since $Since `
    -NewDesign $NewDesign `
    -Version $Version `
    -CommitSubject $CommitSubject `
    -RefKb $RefKb `
    -UpdatedKb $UpdatedKb `
    -KbCommitSubject $KbCommitSubject `
    -KbUpdated $KbUpdated `
    -RefMain $RefMain `
    -AllContext:$AllContext `
    -DesignsOnly:$DesignsOnly `
    -NoRead:$NoRead `
    -PersistUser:$PersistUser `
    -RunRepomix:$RunRepomix `
    -RunDocsRepomix:$RunDocsRepomix `
    -Interactive:$Interactive `
    -CommitChanges:$CommitChanges `
    -StageAll:$StageAll