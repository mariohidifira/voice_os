$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "== Phase 4 evidence bundle =="
Write-Host "Date: 2026-08-25"
Write-Host

& "powershell" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\check_phase4_remote_ready.ps1")
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

& $pythonExe (Join-Path $repoRoot "scripts\build_phase4_evidence_summary.py")
exit $LASTEXITCODE
