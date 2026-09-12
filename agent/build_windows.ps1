# DevOps Monitor Pro - Windows agent build script
# Produces agent/dist/DevOpsMonitorAgent.exe (single-file, no Python needed on client machines).
#
# Usage (PowerShell, from any directory):
#   powershell -ExecutionPolicy Bypass -File agent\build_windows.ps1
#
# Optional parameters:
#   -Python <path>    Python interpreter to use (default: agent\venv\Scripts\python.exe if present, else "python")
#
# The script:
#   1. creates/uses agent\.venv-build with pyinstaller,
#   2. installs the agent runtime requirements into it,
#   3. runs PyInstaller with agent\DevOpsMonitorAgent.spec,
#   4. prints the resulting executable path.
#
# No secrets, tokens or .env files are bundled. The production API URL
# (https://devops-monitor-pro.vercel.app/api) is the compiled default from
# agent/config.py; override at runtime with the API_URL environment variable.

param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

# Resolve repo paths relative to this script (agent/ is its parent).
$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $agentDir
Set-Location $agentDir

# Choose interpreter: explicit param > agent venv > PATH python.
if (-not $Python) {
    $venvPython = Join-Path $agentDir "venv\Scripts\python.exe"
    if (Test-Path $venvPython) { $Python = $venvPython } else { $Python = "python" }
}
Write-Host "== DevOps Monitor Pro agent build ==" -ForegroundColor Cyan
Write-Host "Python: $Python"
& $Python --version

# 1) Build virtualenv with PyInstaller (isolated; does not touch the dev venv).
$buildVenv = Join-Path $agentDir ".venv-build"
if (-not (Test-Path (Join-Path $buildVenv "Scripts\python.exe"))) {
    Write-Host "Creating build virtualenv..."
    & $Python -m venv $buildVenv
}

$buildPython = Join-Path $buildVenv "Scripts\python.exe"

Write-Host "Installing agent requirements + pyinstaller..."
& $buildPython -m pip install --upgrade pip --quiet
& $buildPython -m pip install --quiet -r (Join-Path $agentDir "requirements.txt")
& $buildPython -m pip install --quiet "pyinstaller>=6.3,<7"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

# 2) Run PyInstaller with the committed spec (reproducible).
Write-Host "Running PyInstaller..."
& $buildPython -m PyInstaller (Join-Path $agentDir "DevOpsMonitorAgent.spec") --clean --noconfirm --distpath (Join-Path $agentDir "dist") --workpath (Join-Path $agentDir "build")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$exe = Join-Path $agentDir "dist\DevOpsMonitorAgent.exe"
if (-not (Test-Path $exe)) { throw "Build finished but DevOpsMonitorAgent.exe was not found." }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "BUILD OK" -ForegroundColor Green
Write-Host "  Executable: $exe ($size MB)"
Write-Host "  Test it:    $exe --help   (or double-click to open the enrollment GUI)"
