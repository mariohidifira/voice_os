$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$gitConfig = Join-Path $repoRoot ".git\config"
$reportPath = Join-Path $repoRoot "reports\phase4-remote-readiness.json"

function Invoke-CapturedStep {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Script
  )

  try {
    $lines = & $Script 2>&1
    $output = ($lines | ForEach-Object { "$_" }) -join [Environment]::NewLine
    return @{
      name = $Name
      ok = $true
      output = $output.Trim()
    }
  }
  catch {
    $message = $_.ToString().Trim()
    return @{
      name = $Name
      ok = $false
      output = $message
    }
  }
}

Write-Host "== Phase 4 remote readiness =="
Write-Host "Date: 2026-08-25"
Write-Host

if (-not (Test-Path $gitConfig)) {
  Write-Error "Arquivo .git\config não encontrado em $repoRoot"
}

$results = @(
  @{
    name = "origin_config"
    ok = $true
    output = ((Get-Content $gitConfig | Select-String 'url = ') | ForEach-Object { "$_" }) -join [Environment]::NewLine
  },
  (Invoke-CapturedStep -Name "gh_api_user" -Script { gh api user }),
  (Invoke-CapturedStep -Name "gh_api_repo" -Script { gh api repos/mariohidifira/voice_os }),
  (Invoke-CapturedStep -Name "gh_workflow_list" -Script { gh workflow list --repo mariohidifira/voice_os }),
  (Invoke-CapturedStep -Name "git_ls_remote_origin" -Script { git -C $repoRoot ls-remote origin })
)

foreach ($result in $results) {
  Write-Host "-- $($result.name) --"
  if ($result.output) {
    Write-Host $result.output
  }
  Write-Host
}

$reportDir = Split-Path -Parent $reportPath
if (-not (Test-Path $reportDir)) {
  New-Item -ItemType Directory -Path $reportDir | Out-Null
}

$report = @{
  date = "2026-08-25"
  scope = "phase4_remote_readiness"
  repo = "mariohidifira/voice_os"
  passed = (($results | Where-Object { -not $_.ok }).Count -eq 0)
  steps = $results
}

$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $reportPath
Write-Host "Report written to $reportPath"
