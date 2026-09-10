#!/bin/bash
set -e

# Detect OS
OS="$(uname -s)"

echo "=== iOS Forensic Tools Installer ==="
echo "Detected Platform: $OS"

install_macos() {
    echo "[*] Starting installation for macOS..."

    # Check for Homebrew
    if ! command -v brew &> /dev/null; then
        echo "[*] Homebrew not found. Installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add brew to PATH for this session if it was just installed
        eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    else
        echo "[+] Homebrew is already installed."
    fi

    # Update Homebrew
    echo "[*] Updating Homebrew..."
    brew update

    # Install System Dependencies
    echo "[*] Installing libimobiledevice and USB tools..."
    brew install libimobiledevice ideviceinstaller

    # Check if Python 3 installed
    if ! command -v python3 &> /dev/null; then
        echo "[*] Installing Python 3..."
        brew install python
    else
        echo "[+] Python 3 is already installed."
    fi

    # Check if pipx is installed
    if ! command -v pipx &> /dev/null; then
        echo "[*] Installing pipx (for isolated Python tool management)..."
        brew install pipx
        pipx ensurepath
    else
        echo "[+] pipx is already installed."
    fi

}

install_ubuntu() {
    echo "[*] Starting installation for Ubuntu/Debian..."

    # Check for apt-get to ensure we are on a compatible distro
    if ! command -v apt-get &> /dev/null; then
        echo "[!] Error: 'apt-get' not found. This script supports Ubuntu/Debian."
        exit 1
    fi

    echo "[*] Updating apt package lists..."
    sudo apt update

    echo "[*] Installing system dependencies (libimobiledevice, python3, build tools)..."
    # We include build-essential and dev headers needed for some MVT dependencies
    sudo apt install -y \
        libimobiledevice-utils \
        ideviceinstaller \
        python3 \
        python3-pip \
        python3-venv \
        pipx \
        build-essential \
        libusb-1.0-0-dev \
        libudev-dev \
        git

    echo "[*] Ensuring pipx is in your PATH..."
    pipx ensurepath
    export PATH="$HOME/.local/bin:$PATH"
}

install_common() {
    echo "[*] Common installation steps (if any) can be added here."

    # Install Mobile Verification Toolkit (MVT)
    echo "[*] Installing MVT via pipx..."
    pipx install mvt --force
}

# Main installation logic
if [ "$OS" = "Darwin" ]; then
    install_macos
elif [ "$OS" = "Linux" ]; then
    install_ubuntu
elif [[ "$OS" == MINGW* || "$OS" == CYGWIN* || "$OS" == MSYS* ]]; then
    echo "[!] Windows is not supported."
    exit 1
else
    echo "[!] Unsupported Operating System: $OS"
    exit 1
fi

install_common


echo ""
echo "=== Installation Complete ==="
echo "You can now run:"
echo "  1. idevicebackup2 --version"
echo "  2. mvt-ios version"

# Additional notes for Linux users
if [ "$OS" = "Linux" ]; then
    echo ""
    echo "NOTE (Linux): If your device is not detected, restart the usbmuxd service:"
    echo "  sudo systemctl restart usbmuxd"
fi