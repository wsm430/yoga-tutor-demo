param(
    [ValidateSet("serial", "none", "ble")]
    [string]$Haptic = "serial"
)

$ErrorActionPreference = "Stop"

$webRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $webRoot
Set-Location $projectRoot

$pythonExe = $null
if (Get-Command conda -ErrorAction SilentlyContinue) {
    $condaInfo = conda env list --json | ConvertFrom-Json
    $environment = $condaInfo.envs | Where-Object {
        (Split-Path -Leaf $_) -eq "yoga-tutor"
    } | Select-Object -First 1
    if ($environment) {
        $candidate = Join-Path $environment "python.exe"
        if (Test-Path $candidate) {
            $pythonExe = $candidate
        }
    }
}

if (-not $pythonExe) {
    throw "The yoga-tutor Conda environment was not found. Run: conda env create -f environment.yml"
}

Write-Host "Yoga Tutor is running at http://127.0.0.1:4173" -ForegroundColor Green
Write-Host "Haptic transport: $Haptic" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
& $pythonExe src\web_mvp_server.py --haptic $Haptic
