<#
Sevastopol File Transfer — uninstaller for Windows.
Copyright (c) 2026 Sevastopol. All Rights Reserved. See ..\LICENSE.

Removes what install.ps1 set up: the installed copy, the Desktop shortcut,
and the firewall rule. Run as Administrator (needed to remove the
firewall rule).
#>

$ErrorActionPreference = "SilentlyContinue"

$InstallDir = Join-Path $env:LOCALAPPDATA "LanDrop"
$shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Sevastopol File Transfer.lnk"

Write-Host "Removing firewall rule ..."
Remove-NetFirewallRule -DisplayName "LanDrop"

Write-Host "Removing Desktop shortcut ..."
Remove-Item -Path $shortcutPath -Force

Write-Host "Removing installed files at $InstallDir ..."
Remove-Item -Path $InstallDir -Recurse -Force

Write-Host "Done. Received files were NOT deleted (they're wherever --out-dir pointed, by default your LanDropReceived folder)." -ForegroundColor Green
