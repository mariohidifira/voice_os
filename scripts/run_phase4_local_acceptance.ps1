$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = if ($env:PYTHON) { $env:PYTHON } else { "python" }

& $pythonExe (Join-Path $repoRoot "scripts\run_phase4_local_acceptance.py")
exit $LASTEXITCODE
