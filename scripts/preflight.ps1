[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()

function Write-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $symbol = if ($Passed) { '[PASS]' } else { '[FAIL]' }
    $color = if ($Passed) { 'Green' } else { 'Red' }
    Write-Host ("{0} {1}: {2}" -f $symbol, $Name, $Detail) -ForegroundColor $color
    if (-not $Passed) { $script:failures.Add($Name) }
}

Set-Location -LiteralPath $projectRoot
Write-Host "FORM presentation preflight" -ForegroundColor Cyan
Write-Host ("Project: {0}" -f $projectRoot)
Write-Host ''

$envPath = Join-Path $projectRoot '.env'
$settings = @{}
if (Test-Path -LiteralPath $envPath) {
    Get-Content -LiteralPath $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#\s=]+)\s*=\s*(.*?)\s*$') {
            $settings[$matches[1]] = $matches[2]
        }
    }
}

Write-Check '.env file' (Test-Path -LiteralPath $envPath) 'root configuration file exists'
Write-Check 'API key' ($settings.ContainsKey('OPENAI_API_KEY') -and -not [string]::IsNullOrWhiteSpace($settings['OPENAI_API_KEY'])) 'configured (value hidden)'
Write-Check 'Model' ($settings.ContainsKey('OPENAI_MODEL') -and -not [string]::IsNullOrWhiteSpace($settings['OPENAI_MODEL'])) $(if ($settings['OPENAI_MODEL']) { $settings['OPENAI_MODEL'] } else { 'not configured' })
Write-Check 'Base URL' ($settings.ContainsKey('OPENAI_BASE_URL') -and -not [string]::IsNullOrWhiteSpace($settings['OPENAI_BASE_URL'])) $(if ($settings['OPENAI_BASE_URL']) { $settings['OPENAI_BASE_URL'] } else { 'not configured' })
Write-Check 'Python environment' (Test-Path -LiteralPath (Join-Path $projectRoot '.venv\Scripts\python.exe')) '.venv Python is installed'
Write-Check 'Pose model' (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\models\pose_landmarker_full.task')) 'MediaPipe full-body model is available locally'
Write-Check 'Motion library' (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\motion_library\aistpp\catalog.json')) 'AIST++ catalog is available locally'
Write-Check 'Adavu library' (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\motion_library\adavu\catalog.json')) 'five curated Bharatanatyam family references are available locally'
Write-Check 'Frontend dependencies' (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\node_modules')) 'node_modules exists'

try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 5
    Write-Check 'Backend' ($health.status -eq 'ok') 'http://127.0.0.1:8000 is healthy'
    Write-Check 'Live-agent configuration' ([bool]$health.live_agent_configured) 'backend process loaded an API key'
    Write-Check 'Motion API' ($health.motion_library_clips -ge 15) ("{0} attributed clips loaded" -f $health.motion_library_clips)
} catch {
    Write-Check 'Backend' $false 'not reachable on port 8000'
}

try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 5 -UseBasicParsing
    Write-Check 'Frontend' ($response.StatusCode -eq 200) 'http://127.0.0.1:5173 is ready'
} catch {
    Write-Check 'Frontend' $false 'not reachable on port 5173'
}

Write-Host ''
if ($failures.Count -eq 0) {
    Write-Host 'FORM is ready for rehearsal.' -ForegroundColor Green
    exit 0
}

Write-Host ("Preflight failed: {0}" -f ($failures -join ', ')) -ForegroundColor Red
Write-Host 'Fix the failed checks before presenting.'
exit 1

