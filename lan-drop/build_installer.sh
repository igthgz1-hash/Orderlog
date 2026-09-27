#!/usr/bin/env bash
# Rebuilds dist/LanDropSetup.exe from installer.nsi + the current server.py.
# Run this after any change to server.py/requirements.txt/install.ps1 so the
# packaged installer stays in sync.
#
# Requires NSIS (makensis). On Debian/Ubuntu: sudo apt-get install nsis
# On Windows/macOS: https://nsis.sourceforge.io/Download
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v makensis >/dev/null 2>&1; then
    echo "makensis not found. Install NSIS first (e.g. 'apt-get install nsis' on Debian/Ubuntu)." >&2
    exit 1
fi

mkdir -p dist
makensis installer.nsi
echo "Built: dist/LanDropSetup.exe"
