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
  IfFileExists "$2\.venv\Scripts\python.exe" already_installed check_python

  check_python:
    ; Python itself isn't bundled in this installer (this build environment's
    ; network policy blocks python.org, so it couldn't be fetched to embed).
    ; Detect it's missing before attempting setup, and offer to open the
    ; download page instead of failing deep inside install.ps1.
    nsExec::ExecToStack 'cmd /c where python'
    Pop $4 ; exit code
    Pop $5 ; captured output (unused, but must be popped to keep the stack balanced)
    ${If} $4 != 0
      MessageBox MB_YESNO|MB_ICONQUESTION "Python 3 was not found on this PC — ${APP_NAME} needs it to run.$\r$\n$\r$\nOpen the Python download page now? After installing (check 'Add python.exe to PATH' during setup), run ${APP_NAME} again." IDYES open_python_page
      Goto python_missing_end
      open_python_page:
        ExecShell "open" "https://www.python.org/downloads/windows/"
      python_missing_end:
      Abort
    ${EndIf}
    Goto do_install

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
    Goto copy_credentials

  already_installed:
    DetailPrint "Already set up on this PC — launching..."
    Goto copy_credentials

  copy_credentials:
    ; If a credentials.json is sitting next to this .exe (i.e. you copied
    ; both files together onto this PC), pick it up automatically so Google
    ; Drive backup doesn't need a manual copy into %LOCALAPPDATA%\LanDrop.
    ; token.json is never copied this way — that one is created fresh by
    ; each PC's own one-time browser sign-in and should stay per-machine.
    IfFileExists "$EXEDIR\credentials.json" 0 launch
      DetailPrint "Found credentials.json next to the installer — installing it..."
      CopyFiles /SILENT "$EXEDIR\credentials.json" "$2\credentials.json"

  launch:
    DetailPrint "Starting ${APP_NAME}..."
    ; --backup-to-drive is safe to pass unconditionally: if credentials.json
    ; isn't present yet in %LOCALAPPDATA%\LanDrop on this PC, drive_backup.py
    ; just logs that to the console and file transfer keeps working normally
    ; (see README.md "Google Drive backup" for the one-time per-PC setup).
    Exec '"cmd.exe" /c start "${APP_NAME}" "$2\.venv\Scripts\python.exe" "$2\server.py" --name "%COMPUTERNAME%" --backup-to-drive'
SectionEnd
