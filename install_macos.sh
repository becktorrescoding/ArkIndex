#!/bin/bash
set -e

echo "============================================================"
echo "  Image to PDF Converter - macOS Installer"
echo "============================================================"
echo ""

ok()   { echo "     ✓ $1"; }
info() { echo "     $1"; }
fail() { echo "     ✗ ERROR: $1"; exit 1; }

# 1. Homebrew
echo "[1/5] Checking for Homebrew..."
if ! command -v brew &>/dev/null; then
    info "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
        || fail "Could not install Homebrew. Visit https://brew.sh"
    # Add brew to PATH for Apple Silicon and Intel
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)" \
                                    || eval "$(/usr/local/bin/brew shellenv)"
    ok "Homebrew installed."
else
    ok "Homebrew found: $(brew --version | head -1)"
fi

# 2. Python 3.9+
echo ""
echo "[2/5] Checking for Python 3.9+..."
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &>/dev/null; then
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
            PYTHON="$cmd"; break
        fi
    fi
done
if [[ -z "$PYTHON" ]]; then
    info "Python 3.9+ not found. Installing via Homebrew..."
    brew install python@3.12
    PYTHON="python3.12"
    ok "Python 3.12 installed."
else
    ok "Found $PYTHON ($($PYTHON --version))"
fi

# 3. Tesseract
echo ""
echo "[3/5] Checking for Tesseract OCR..."
if ! command -v tesseract &>/dev/null; then
    info "Installing Tesseract via Homebrew..."
    brew install tesseract
    ok "Tesseract installed."
else
    ok "Tesseract found: $(tesseract --version 2>&1 | head -1)"
fi

# 4. Ghostscript
echo ""
echo "[4/5] Checking for Ghostscript..."
if ! command -v gs &>/dev/null; then
    info "Installing Ghostscript via Homebrew..."
    brew install ghostscript
    ok "Ghostscript installed."
else
    ok "Ghostscript found: $(gs --version)"
fi

# 5. Python packages
echo ""
echo "[5/5] Installing Python packages..."
$PYTHON -m pip install --upgrade pip --quiet
$PYTHON -m pip install --upgrade ocrmypdf pytesseract Pillow pymupdf \
    || fail "Failed to install Python packages."
ok "Python packages installed."

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "  Run the app with:  $PYTHON app.py"
echo "============================================================"
echo ""
