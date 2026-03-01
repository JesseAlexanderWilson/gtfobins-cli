#!/bin/bash
# GTFOBins CLI - Install Script

set -e

REPO="https://github.com/JesseAlexanderWilson/gtfobins-cli"
INSTALL_DIR="/opt/gtfobins-cli"
SYMLINK="/usr/local/bin/gtfobins"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo."
    exit 1
fi

# Check for git
if ! command -v git &> /dev/null; then
    echo "git is required. Install it with: sudo apt install git"
    exit 1
fi

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "python3 is required. Install it with: sudo apt install python3"
    exit 1
fi

echo "[*] Cloning gtfobins-cli to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR" ]; then
    echo "[*] Directory already exists, pulling latest..."
    git -C "$INSTALL_DIR" pull
else
    git clone "$REPO" "$INSTALL_DIR"
fi

echo "[*] Creating API directory..."
mkdir -p "$INSTALL_DIR/API"

echo "[*] Setting permissions..."
chmod +x "$INSTALL_DIR/gtfobins.py"

echo "[*] Creating symlink at $SYMLINK..."
ln -sf "$INSTALL_DIR/gtfobins.py" "$SYMLINK"

echo "[*] Downloading GTFOBins database..."
gtfobins --update

echo ""
echo "[+] Done! Run 'gtfobins --help' to get started."
