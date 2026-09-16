# DevOps Monitor Pro - Windows agent build script
# Produces:
#   agent/dist/DevOpsMonitorAgent.exe          (portable single-file agent)
#   agent/dist/DevOpsMonitorAgent-Setup.exe    (client installer, if Inno Setup is installed)
#
# Usage (PowerShell, from any directory):
#   powershell -ExecutionPolicy Bypass -File agent\build_windows.ps1
#
# Optional parameters:
#   -Python <path>    Python interpreter to use (default: agent\venv\Scripts\python.exe if present, else "python")
#   -ApiUrl <url>     Override the production API URL from agent\build_config.ps1
#   -SkipInstaller    Only build the portable exe (skip Inno Setup even if installed)
#
# The API URL is the ONE centralized configuration value (agent\build_config.ps1).
# http:// URLs are rejected so localhost can never ship in a client build.
#
# No secrets, tokens or .env files are bundled.

param(
    [string]$Python = "",
    [string]$ApiUrl = "",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

# Resolve repo paths relative to this script (agent/ is its parent).
$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $agentDir

# ---------------------------------------------------------------------------
# 1) Central configuration (agent\build_config.ps1) + optional override
# ---------------------------------------------------------------------------
$cfg = Join-Path $agentDir "build_config.ps1"
if (Test-Path $cfg) { . $cfg }

if (-not $ApiUrl) {
    if (Get-Variable -Name "ApiUrl" -Scope Script -ErrorAction SilentlyContinue) {
        $ApiUrl = $script:ApiUrl
    }
}
if (-not $ApiUrl) { throw "No API URL configured. Set `$ApiUrl in agent\build_config.ps1." }

# Security guard: never bake an insecure URL into a client build.
if ($ApiUrl -notmatch "^https://") {
    throw "Refusing to build: API URL must use HTTPS for production (got '$ApiUrl')."
}
if ($ApiUrl -match "localhost|127\.0\.0\.1") {
    throw "Refusing to build: localhost API URLs must never ship to clients."
}

$AppVersion = if (Get-Variable -Name "AppVersion" -Scope Script -ErrorAction SilentlyContinue) { $script:AppVersion } else { "1.0.0" }

Write-Host "== DevOps Monitor Pro agent build ==" -ForegroundColor Cyan
Write-Host "API URL:   $ApiUrl"
Write-Host "Version:   $AppVersion"

# ---------------------------------------------------------------------------
# 2) Interpreter + build virtualenv with PyInstaller (isolated from dev venv)
# ---------------------------------------------------------------------------
if (-not $Python) {
    $venvPython = Join-Path $agentDir "venv\Scripts\python.exe"
    if (Test-Path $venvPython) { $Python = $venvPython } else { $Python = "python" }
}
Write-Host "Python:    $Python"
& $Python --version

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

# ---------------------------------------------------------------------------
# 3) Generate the runtime hook that embeds the production API URL.
#    (Public URL only - never secrets. Overridable at runtime via API_URL env.)
# ---------------------------------------------------------------------------
$hookFile = Join-Path $agentDir "_runtime_hook.py"
$hookTemplate = Get-Content (Join-Path $agentDir "runtime_hook.py.template") -Raw
$hookTemplate.Replace("__API_URL__", $ApiUrl) | Set-Content -Path $hookFile -Encoding UTF8
Write-Host "Runtime hook written: $hookFile (API_URL=$ApiUrl)"

# ---------------------------------------------------------------------------
# 4) Run PyInstaller with the committed spec (reproducible)
# ---------------------------------------------------------------------------
Write-Host "Running PyInstaller..."
& $buildPython -m PyInstaller (Join-Path $agentDir "DevOpsMonitorAgent.spec") --clean --noconfirm --distpath (Join-Path $agentDir "dist") --workpath (Join-Path $agentDir "build")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$exe = Join-Path $agentDir "dist\DevOpsMonitorAgent.exe"
if (-not (Test-Path $exe)) { throw "Build finished but DevOpsMonitorAgent.exe was not found." }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "PORTABLE AGENT OK" -ForegroundColor Green
Write-Host "  Executable: $exe ($size MB)"

# ---------------------------------------------------------------------------
# 5) Client installer (Inno Setup) - built automatically when ISCC is found
# ---------------------------------------------------------------------------
if ($SkipInstaller) {
    Write-Host ""
    Write-Host "Skipping installer build (-SkipInstaller)."
    return
}

$iscc = $null
foreach ($candidate in @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)) {
    if ($candidate -and (Test-Path $candidate)) { $iscc = $candidate; break }
}
if (-not $iscc) {
    $cmd = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    # Fallback: scan the concrete install roots where Inno Setup typically lives,
    # including the winget default user install (%LOCALAPPDATA%\Programs).
    $scanRoots = @(
        "C:\Program Files",
        "C:\Program Files (x86)"
    )
    $localApps = $env:LOCALAPPDATA + '\Programs'
    if (Test-Path $localApps) { $scanRoots += $localApps }
    foreach ($scanRoot in $scanRoots) {
        if ((Test-Path $scanRoot) -eq $false) { continue }
        $dirs = Get-ChildItem $scanRoot -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'Inno Setup' }
        foreach ($d in $dirs) {
            $c = Join-Path $d.FullName 'ISCC.exe'
            if (Test-Path $c) { $iscc = $c; break }
        }
        if ($iscc) { break }
    }
}

if ($iscc) {
    Write-Host ""
    Write-Host "Building installer with Inno Setup..."
    & $iscc "/DApiUrl=$ApiUrl" (Join-Path $agentDir "installer\DevOpsMonitorAgent.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed." }

    $setup = Join-Path $agentDir "dist\DevOpsMonitorAgent-Setup.exe"
    if (Test-Path $setup) {
        $setupSize = [math]::Round((Get-Item $setup).Length / 1MB, 1)
        Write-Host ""
        Write-Host "SETUP INSTALLER OK" -ForegroundColor Green
        Write-Host "  Installer:  $setup ($setupSize MB)"
    } else {
        throw "Inno Setup ran but DevOpsMonitorAgent-Setup.exe was not found."
    }
} else {
    Write-Host ""
    Write-Host "NOTE: Inno Setup 6 not found - built the portable agent only." -ForegroundColor Yellow
    Write-Host "      Install Inno Setup (winget install JRSoftware.InnoSetup) to also"
    Write-Host "      produce dist\DevOpsMonitorAgent-Setup.exe (recommended for clients)."
}
