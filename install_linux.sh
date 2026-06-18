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
    fail "Unsupported distro. Install manually: python3 tesseract ghostscript"
fi
info "Detected package manager: $PKG_MANAGER"

SUDO=""
[[ $EUID -ne 0 ]] && SUDO="sudo" && info "sudo required for system packages — you may be prompted for your password."

# 1. Refresh package index
echo ""
echo "[1/5] Refreshing package index..."
case "$PKG_MANAGER" in
    apt)     $SUDO apt-get update -qq ;;
    dnf)     $SUDO dnf check-update -q || true ;;
    pacman)  $SUDO pacman -Sy --noconfirm ;;
esac
ok "Package index refreshed."

# 2. Python 3.9+
echo ""
echo "[2/5] Checking for Python 3.9+..."
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
        major="${ver%.*}"
        minor="${ver#*.}"
        if [[ "$major" -ge 3 && "$minor" -ge 9 ]] 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    info "Installing Python 3..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y python3 python3-pip ;;
        dnf)     $SUDO dnf install -y python3 python3-pip ;;
        pacman)  $SUDO pacman -S --noconfirm python python-pip ;;
    esac
    PYTHON="python3"
fi
ok "Python found: $($PYTHON --version)"

# 3. Tesseract
echo ""
echo "[3/5] Checking for Tesseract OCR..."
if ! command -v tesseract &>/dev/null; then
    info "Installing Tesseract OCR..."
    case "$PKG_MANAGER" in
        apt)     $SUDO apt-get install -y tesseract-ocr ;;
        dnf)     $SUDO dnf install -y tesseract ;;
        pacman)  $SUDO pacman -S --noconfirm tesseract ;;
    esac
    ok "Tesseract installed."
else
    ok "Tesseract found: $(tesseract --version 2>&1 | head -1)"
fi

# 4. Ghostscript
echo ""
echo "[4/5] Checking for Ghostscript..."
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




# 5. Python packages
echo ""
echo "[5/5] Installing Python packages..."
# PEP 668: modern Debian/Ubuntu block system-wide pip installs.
# Disable set -e so we can try multiple strategies.
set +e

# First, upgrade pip itself (may need --break-system-packages or --user)
$PYTHON -m ensurepip --upgrade 2>/dev/null || true
$PYTHON -m pip install --upgrade pip --quiet --break-system-packages 2>/dev/null || \
$PYTHON -m pip install --upgrade pip --quiet --user 2>/dev/null || \
$PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true

PIP_OK=0

# Strategy 1: --break-system-packages (pip 23.1+)
echo "     Trying --break-system-packages..."
$PYTHON -m pip install ocrmypdf pytesseract Pillow pymupdf --break-system-packages
[[ $? -eq 0 ]] && PIP_OK=1

# Strategy 2: --user (bypasses PEP 668)
if [[ $PIP_OK -eq 0 ]]; then
    echo "     Trying --user..."
    $PYTHON -m pip install ocrmypdf pytesseract Pillow pymupdf --user
    [[ $? -eq 0 ]] && PIP_OK=1
fi

# Strategy 3: plain install (non-PEP-668 systems)
if [[ $PIP_OK -eq 0 ]]; then
    echo "     Trying plain pip install..."
    $PYTHON -m pip install ocrmypdf pytesseract Pillow pymupdf
    [[ $? -eq 0 ]] && PIP_OK=1
fi

set -e

if [[ $PIP_OK -eq 1 ]]; then
    ok "Python packages installed."
else
    fail "pip install failed. Create a venv instead:
    $PYTHON -m venv .venv && source .venv/bin/activate
    pip install ocrmypdf pytesseract Pillow pymupdf"
fi

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "  Run the app with:  $PYTHON ArkIndex.py"
echo "============================================================"
echo ""
