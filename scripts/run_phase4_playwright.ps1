$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$playwrightCmd = Join-Path $repoRoot "node_modules\.bin\playwright.cmd"
$specPath = Join-Path $repoRoot "apps\web\e2e\phase4-whatsapp-simulator.spec.ts"
$configPath = Join-Path $repoRoot "apps\web\playwright.config.ts"

& $playwrightCmd test $specPath "--config=$configPath" "--reporter=line"
exit $LASTEXITCODE
