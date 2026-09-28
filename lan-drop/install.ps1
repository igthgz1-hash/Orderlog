<#
Sevastopol File Transfer - installer for Windows.
Copyright (c) 2026 Sevastopol. All Rights Reserved. See ..\LICENSE.

Installs into %LOCALAPPDATA%\LanDrop, sets up a Python virtual
environment with its dependencies, opens the firewall port it needs, and
creates a Desktop shortcut to start it.

Usage (run from PowerShell AS ADMINISTRATOR, from inside the lan-drop
folder - right-click install.ps1 -> "Run with PowerShell", or):
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
    .\install.ps1
#>

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "Sevastopol File Transfer - Installer" -ForegroundColor Cyan
Write-Host "Copyright (c) 2026 Sevastopol. All Rights Reserved." -ForegroundColor Cyan
Write-Host ""

function Fail($message) {
    Write-Host $message -ForegroundColor Red
    exit 1
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Fail "Please re-run this script as Administrator (needed to add the firewall rule). Right-click PowerShell -> 'Run as administrator', then run install.ps1 again."
}

$SourceDir = $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA "LanDrop"
$RepoRoot = Split-Path $SourceDir -Parent
$LicenseSource = Join-Path $RepoRoot "LICENSE"

Write-Host "Installing LAN Drop to $InstallDir ..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $SourceDir "server.py") -Destination $InstallDir -Force
Copy-Item -Path (Join-Path $SourceDir "requirements.txt") -Destination $InstallDir -Force
Copy-Item -Path (Join-Path $SourceDir "drive_backup.py") -Destination $InstallDir -Force
Copy-Item -Path (Join-Path $SourceDir "requirements-drive.txt") -Destination $InstallDir -Force
if (Test-Path $LicenseSource) {
    Copy-Item -Path $LicenseSource -Destination $InstallDir -Force
}

# Prefer "python" (the common case), but fall back to the "py" launcher --
# it's what a Python install just performed by installer.nsi in this same
# run actually shows up as, since "py" always lands in C:\Windows (already
# on PATH) while a brand new "python" directory isn't visible yet to this
# already-running process tree.
$pythonExe = "python"
$pythonArgsPrefix = @()
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonExe = "py"
        $pythonArgsPrefix = @("-3")
    } else {
        Fail "Python was not found on PATH. Install Python 3 from https://www.python.org/downloads/windows/ (check 'Add python.exe to PATH' during setup), then run this installer again."
    }
}

$venvDir = Join-Path $InstallDir ".venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating Python virtual environment ..."
    & $pythonExe @pythonArgsPrefix -m venv $venvDir
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
Write-Host "Installing dependencies ..."
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r (Join-Path $InstallDir "requirements.txt")
Write-Host "Installing Google Drive backup dependencies ..."
& $venvPython -m pip install --quiet -r (Join-Path $InstallDir "requirements-drive.txt")

Write-Host "Opening firewall port $Port (TCP) ..."
if (-not (Get-NetFirewallRule -DisplayName "LanDrop" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "LanDrop" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
} else {
    Write-Host "Firewall rule 'LanDrop' already exists, leaving it as-is."
}

Write-Host "Creating Desktop shortcut ..."
$shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Sevastopol File Transfer.lnk"
$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $venvPython
$shortcut.Arguments = "`"$InstallDir\server.py`" --name `"$env:COMPUTERNAME`" --port $Port"
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = "shell32.dll,44"
$shortcut.Description = "Start Sevastopol File Transfer (c) 2026 Sevastopol"
$shortcut.Save()

Write-Host ""
Write-Host "Done. Double-click 'Sevastopol File Transfer' on your Desktop to start the server." -ForegroundColor Green
Write-Host "A console window will open showing a QR code and URL - scan it from your phone (same Wi-Fi network)."
Write-Host "To remove it later, run uninstall.ps1 from this same folder."
Write-Host ""
Write-Host "Sevastopol File Transfer - Copyright (c) 2026 Sevastopol. All Rights Reserved." -ForegroundColor Cyan
