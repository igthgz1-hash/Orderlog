#!/usr/bin/env bash
# LAN Drop installer for macOS/Linux.
# Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
#
# Installs into ~/.local/share/lan-drop, sets up a virtual environment with
# dependencies, and prints a launch command. Run from inside the lan-drop
# folder:
#   ./install.sh
set -euo pipefail

echo "LAN Drop Installer"
echo "Copyright (c) 2026 Sevastopol. All Rights Reserved."
echo ""

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/lan-drop"
REPO_ROOT="$(dirname "$SOURCE_DIR")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Install Python 3 first (e.g. 'brew install python3' on macOS, or your distro's package manager on Linux)." >&2
    exit 1
fi

echo "Installing LAN Drop to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp "$SOURCE_DIR/server.py" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SOURCE_DIR/drive_backup.py" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements-drive.txt" "$INSTALL_DIR/"
if [ -f "$REPO_ROOT/LICENSE" ]; then
    cp "$REPO_ROOT/LICENSE" "$INSTALL_DIR/"
fi

if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "Creating Python virtual environment ..."
    python3 -m venv "$INSTALL_DIR/.venv"
fi

echo "Installing dependencies ..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

LAUNCH_CMD="$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/server.py --name \"$(hostname)\""

BIN_LINK="$HOME/.local/bin/lan-drop"
mkdir -p "$HOME/.local/bin"
cat > "$BIN_LINK" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/server.py" "\$@"
EOF
chmod +x "$BIN_LINK"

echo ""
echo "Done. If ~/.local/bin is on your PATH, just run:"
echo "  lan-drop --name \"$(hostname)\""
echo ""
echo "Otherwise run it directly with:"
echo "  $LAUNCH_CMD"
echo ""
echo "macOS may prompt to allow incoming network connections the first time — allow it."
echo "To remove LAN Drop later, run: rm -rf \"$INSTALL_DIR\" \"$BIN_LINK\""
echo ""
echo "LAN Drop — Copyright (c) 2026 Sevastopol. All Rights Reserved."
