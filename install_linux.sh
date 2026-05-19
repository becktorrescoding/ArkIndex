#!/bin/bash
set -e

echo "============================================================"
echo "  Image to PDF Converter - Linux Installer"
echo "============================================================"
echo ""

ok()   { echo "     ✓ $1"; }
info() { echo "     $1"; }
fail() { echo "     ✗ ERROR: $1"; exit 1; }

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
else
    fail "Unsupported distro. Install manually: python3 tesseract ghostscript poppler-utils"
fi
info "Detected package manager: $PKG_MANAGER"

SUDO=""
[[ $EUID -ne 0 ]] && SUDO="sudo" && info "sudo required for system packages — you may be prompted for your password."

# 1. Refresh package index
echo ""
echo "[1/6] Refreshing package index..."
case "$PKG_MANAGER" in
    apt)     $SUDO apt-get update -qq ;;
    dnf)     $SUDO dnf check-update -q || true ;;
    pacman)  $SUDO pacman -Sy --noconfirm --quiet ;;
esac
ok "Package index refreshed."

# 2. Python 3.9+
echo ""
echo "[2/6] Checking for Python 3.9+..."
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
            PYTHON="$cmd"; break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    info "Python 3.9+ not found. Installing..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y python3 python3-pip python3-tk ;;
        dnf)     $SUDO dnf install -y python3 python3-pip python3-tkinter ;;
        pacman)  $SUDO pacman -S --noconfirm python python-pip tk ;;
    esac
    PYTHON="python3"
    ok "Python installed: $($PYTHON --version)"
else
    ok "Found $PYTHON ($($PYTHON --version))"
    # Ensure pip + tkinter are present
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y python3-pip python3-tk -qq ;;
        dnf)     $SUDO dnf install -y python3-pip python3-tkinter -q ;;
        pacman)  $SUDO pacman -S --noconfirm python-pip tk --needed --quiet ;;
    esac
fi

# 3. Tesseract
echo ""
echo "[3/6] Checking for Tesseract OCR..."
if ! command -v tesseract &>/dev/null; then
    info "Installing Tesseract..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y tesseract-ocr ;;
        dnf)     $SUDO dnf install -y tesseract ;;
        pacman)  $SUDO pacman -S --noconfirm tesseract tesseract-data-eng ;;
    esac
    ok "Tesseract installed."
else
    ok "Tesseract found: $(tesseract --version 2>&1 | head -1)"
fi

# 4. Ghostscript
echo ""
echo "[4/6] Checking for Ghostscript..."
if ! command -v gs &>/dev/null; then
    info "Installing Ghostscript..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y ghostscript ;;
        dnf)     $SUDO dnf install -y ghostscript ;;
        pacman)  $SUDO pacman -S --noconfirm ghostscript ;;
    esac
    ok "Ghostscript installed."
else
    ok "Ghostscript found: $(gs --version)"
fi

# 5. Poppler (pdftoppm)
echo ""
echo "[5/6] Checking for Poppler (pdftoppm)..."
if ! command -v pdftoppm &>/dev/null; then
    info "Installing Poppler..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y poppler-utils ;;
        dnf)     $SUDO dnf install -y poppler-utils ;;
        pacman)  $SUDO pacman -S --noconfirm poppler ;;
    esac
    ok "Poppler installed."
else
    ok "Poppler found: $(pdftoppm -v 2>&1 | head -1)"
fi

# 6. Python packages
echo ""
echo "[6/6] Installing Python packages..."
# PEP 668: modern Debian/Ubuntu block system-wide pip installs.
# --break-system-packages bypasses this for dedicated setup scripts.
PIP_FLAGS="--break-system-packages"
$PYTHON -m pip install --upgrade pip --quiet $PIP_FLAGS 2>/dev/null || true
$PYTHON -m pip install --upgrade ocrmypdf pytesseract Pillow pymupdf $PIP_FLAGS \
    || fail "Failed to install Python packages. Try running with sudo or inside a virtual environment."
ok "Python packages installed."

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "  Run the app with:  $PYTHON app.py"
echo "============================================================"
echo ""
