; Sevastopol File Transfer — Windows one-click installer + launcher
; Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
;
; This NSIS script builds "Sevastopol File Transfer v1.exe": a single
; double-clickable Windows program that sets everything up on first run
; (venv, dependencies, firewall rule, Desktop shortcut — via install.ps1,
; the same already-tested logic) and then, every time it's run afterward,
; just launches the server immediately in its own console window. One EXE
; covers both "first time on a new PC" and "run it again tomorrow".
;
; Build with: makensis installer.nsi   (run from inside the lan-drop folder)
; Requires: NSIS 3.x (https://nsis.sourceforge.io/), or on Debian/Ubuntu:
;   apt-get install nsis

!include "LogicLib.nsh"

!define APP_NAME "Sevastopol File Transfer"
!define APP_VERSION "v1"
!define COMPANY "Sevastopol"
!define YEAR "2026"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "dist\${APP_NAME} ${APP_VERSION}.exe"
InstallDir "$TEMP\SevastopolFileTransferSetup"
RequestExecutionLevel admin
ShowInstDetails show
BrandingText "${APP_NAME} ${APP_VERSION} — Copyright (c) ${YEAR} ${COMPANY}"

Section "Run"
  DetailPrint "${APP_NAME} ${APP_VERSION}"
  DetailPrint "Copyright (c) ${YEAR} ${COMPANY}. All Rights Reserved."
  DetailPrint ""

  StrCpy $2 "$LOCALAPPDATA\LanDrop"

  ; Fast path: already set up on this PC (from a previous run) — skip
  ; straight to launching, no need to re-run pip/firewall/shortcut steps.
  IfFileExists "$2\.venv\Scripts\python.exe" already_installed do_install

  do_install:
    DetailPrint "First time on this PC — running one-time setup..."
    SetOutPath "$INSTDIR"
    File "server.py"
    File "requirements.txt"
    File "drive_backup.py"
    File "requirements-drive.txt"
    File "install.ps1"
    File "..\LICENSE"

    nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\install.ps1"'
    Pop $0

    SetOutPath "$TEMP"
    RMDir /r "$INSTDIR"

    ${If} $0 != 0
      MessageBox MB_ICONEXCLAMATION "Setup failed (exit code $0). Check the details in this window (scroll up) for what went wrong — the most common cause is Python not being installed yet."
      Abort
    ${EndIf}
    Goto launch

  already_installed:
    DetailPrint "Already set up on this PC — launching..."

  launch:
    DetailPrint "Starting ${APP_NAME}..."
    Exec '"cmd.exe" /c start "${APP_NAME}" "$2\.venv\Scripts\python.exe" "$2\server.py" --name "%COMPUTERNAME%"'
SectionEnd
