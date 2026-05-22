#requires -Version 5.1
<#
.SYNOPSIS
    Builds ScreenRec: PyInstaller bundle -> optional Inno Setup installer.

.DESCRIPTION
    Run from the project root:  pwsh -File build.ps1
    Outputs:
      dist\ScreenRec\           — PyInstaller bundle (run ScreenRec.exe inside)
      installer\Output\ScreenRec_Setup.exe  — single-file installer (if Inno Setup present)
#>

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    throw "Venv missing. Run:  python -m venv .venv ;  .venv\Scripts\pip install -r requirements.txt"
}

# 1) Regenerate icons (cheap, idempotent)
Write-Host "==> Generating icons" -ForegroundColor Cyan
& $venvPy (Join-Path $root "build_tools\make_icons.py")

# 2) Ensure ffmpeg is bundled
$ffmpegBin = Join-Path $root "src\resources\ffmpeg\ffmpeg.exe"
if (-not (Test-Path $ffmpegBin)) {
    throw "ffmpeg.exe missing at $ffmpegBin. Download essentials build from https://www.gyan.dev/ffmpeg/builds/ and place ffmpeg.exe there."
}
Write-Host "==> ffmpeg present: $([math]::Round((Get-Item $ffmpegBin).Length / 1MB, 1)) MB" -ForegroundColor Cyan

# 3) Clean previous build
Write-Host "==> Cleaning build/ and dist/" -ForegroundColor Cyan
Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "dist") -ErrorAction SilentlyContinue

# 4) PyInstaller
Write-Host "==> Running PyInstaller" -ForegroundColor Cyan
& $venvPy -m PyInstaller `
    --noconfirm `
    --windowed `
    --name TrayRecorder `
    --icon (Join-Path $root "src\resources\icon.ico") `
    --add-data ("src\resources;resources") `
    --hidden-import "win10toast_click" `
    --hidden-import "soundcard" `
    --hidden-import "soundfile" `
    (Join-Path $root "screenrec.py")

$exe = Join-Path $root "dist\TrayRecorder\TrayRecorder.exe"
if (-not (Test-Path $exe)) {
    throw "PyInstaller did not produce $exe"
}
Write-Host "==> Built: $exe" -ForegroundColor Green

# 5) Inno Setup (optional — produces single-file installer)
$iscc = $null
foreach ($p in @("C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe")) {
    if (Test-Path $p) { $iscc = $p; break }
}
if ($null -eq $iscc) {
    Write-Host ""
    Write-Host "==> Skipping installer (Inno Setup not found)" -ForegroundColor Yellow
    Write-Host "    To produce ScreenRec_Setup.exe, install Inno Setup 6 from https://jrsoftware.org/isdl.php"
    Write-Host "    Then re-run build.ps1."
    Write-Host ""
    Write-Host "Done. Run the app from:  $exe" -ForegroundColor Green
    return
}

Write-Host "==> Running Inno Setup" -ForegroundColor Cyan
$iss = Join-Path $root "installer\setup.iss"
& $iscc /Qp $iss
$setup = Join-Path $root "installer\Output\TrayRecorder_Setup.exe"
if (Test-Path $setup) {
    Write-Host ""
    Write-Host "==> Installer: $setup" -ForegroundColor Green
    Write-Host "    Size: $([math]::Round((Get-Item $setup).Length / 1MB, 1)) MB"
} else {
    throw "Inno Setup did not produce $setup"
}
