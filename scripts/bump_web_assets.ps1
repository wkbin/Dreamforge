param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $repoRoot "scripts\web_asset_version.py"

if ([string]::IsNullOrWhiteSpace($Version)) {
    py -3 $scriptPath --bump
} else {
    py -3 $scriptPath --version $Version
}
