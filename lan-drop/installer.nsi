; LAN Drop — Windows installer
; Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
;
; This NSIS script builds LanDropSetup.exe: a real double-clickable Windows
; installer that wraps install.ps1 (the same, already-tested logic) with a
; UAC elevation prompt and a simple progress window, so nobody has to open
; PowerShell manually.
;
; Build with: makensis installer.nsi   (run from inside the lan-drop folder)
; Requires: NSIS 3.x (https://nsis.sourceforge.io/), or on Debian/Ubuntu:
;   apt-get install nsis

!include "LogicLib.nsh"

!define APP_NAME "LAN Drop"
!define COMPANY "Sevastopol"
!define YEAR "2026"

Name "${APP_NAME}"
OutFile "dist\LanDropSetup.exe"
InstallDir "$TEMP\LanDropSetup"
RequestExecutionLevel admin
ShowInstDetails show
BrandingText "${APP_NAME} — Copyright (c) ${YEAR} ${COMPANY}"

Section "Install"
  DetailPrint "${APP_NAME} Installer"
  DetailPrint "Copyright (c) ${YEAR} ${COMPANY}. All Rights Reserved."
  DetailPrint ""

  SetOutPath "$INSTDIR"
  File "server.py"
  File "requirements.txt"
  File "drive_backup.py"
  File "requirements-drive.txt"
  File "install.ps1"
  File "..\LICENSE"

  DetailPrint "Running setup (this installs to %LOCALAPPDATA%\LanDrop) ..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\install.ps1"'
  Pop $0

  ; Clean up the staging copy — install.ps1 already copied what it needs
  ; into %LOCALAPPDATA%\LanDrop.
  SetOutPath "$TEMP"
  RMDir /r "$INSTDIR"

  ${If} $0 == 0
    MessageBox MB_OK "${APP_NAME} installed successfully.$\r$\n$\r$\nLook for the '${APP_NAME}' shortcut on your Desktop.$\r$\n$\r$\nCopyright (c) ${YEAR} ${COMPANY}. All Rights Reserved."
  ${Else}
    MessageBox MB_ICONEXCLAMATION "Setup finished with exit code $0. Check the details in this window (scroll up) for what went wrong — the most common cause is Python not being installed yet."
  ${EndIf}
SectionEnd
