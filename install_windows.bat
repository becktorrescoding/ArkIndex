@echo off
setlocal EnableDelayedExpansion
title Image to PDF Converter - Installer

echo ============================================================
echo   Image to PDF Converter - Windows Installer
echo ============================================================
echo.

:: Step 1: Python
echo [1/6] Checking for Python 3.9+...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo      Python not found. Installing via winget...
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo      winget failed. Trying direct download...
        curl -Lo "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
        "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1
        if !errorlevel! neq 0 (
            echo      ERROR: Could not install Python automatically.
            echo      Please install Python 3.12+ from https://www.python.org/downloads/ or from the Microsoft Store
            pause & exit /b 1
        )
    )
    call refreshenv >nul 2>&1
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
    echo      Python installed successfully.
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo      Found Python !PY_VER!
)

:: Step 2: pip
echo.
echo [2/6] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo      Done.

:: Step 3: Tesseract
echo.
echo [3/6] Checking for Tesseract OCR...
tesseract --version >nul 2>&1
if %errorlevel% neq 0 (
    echo      Tesseract not found. Installing via winget...
    winget install --id UB-Mannheim.TesseractOCR --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo      winget failed. Downloading installer directly...
        curl -Lo "%TEMP%\tesseract_installer.exe" "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
        "%TEMP%\tesseract_installer.exe" /S
        if !errorlevel! neq 0 (
            echo      ERROR: Could not install Tesseract automatically.
            echo      Please install from: https://github.com/UB-Mannheim/tesseract/wiki
            pause & exit /b 1
        )
    )
    set "PATH=%PATH%;C:\Program Files\Tesseract-OCR"
    echo      Tesseract installed.
) else (
    echo      Tesseract already installed.
)

:: Step 4: Ghostscript
echo.
echo [4/6] Checking for Ghostscript...
gswin64c --version >nul 2>&1 || gswin32c --version >nul 2>&1
if %errorlevel% neq 0 (
    echo      Ghostscript not found. Installing via winget...
    winget install --id ArtifexSoftware.GhostScript --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo      ERROR: Could not install Ghostscript automatically.
        echo      Please install from: https://www.ghostscript.com/releases/gsdnld.html
        pause & exit /b 1
    )
    echo      Ghostscript installed.
) else (
    echo      Ghostscript already installed.
)

:: Step 5: Poppler
echo.
echo [5/6] Checking for Poppler (pdftoppm)...
pdftoppm -v >nul 2>&1
if %errorlevel% neq 0 (
    echo      Poppler not found. Installing via winget...
    winget install --id oscarfonts.poppler --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo      winget package unavailable. Downloading release zip...
        curl -Lo "%TEMP%\poppler.zip" "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.02.0-0/Release-24.02.0-0.zip"
        powershell -Command "Expand-Archive -Path '%TEMP%\poppler.zip' -DestinationPath 'C:\poppler' -Force"
        powershell -Command "[Environment]::SetEnvironmentVariable('PATH', $env:PATH + ';C:\poppler\poppler-24.02.0\Library\bin', 'Machine')"
        set "PATH=%PATH%;C:\poppler\poppler-24.02.0\Library\bin"
        if !errorlevel! neq 0 (
            echo      ERROR: Could not install Poppler automatically.
            echo      Download from: https://github.com/oschwartz10612/poppler-windows/releases
            echo      Extract and add the bin\ folder to your system PATH.
            pause & exit /b 1
        )
    )
    echo      Poppler installed. Restart your terminal for PATH changes to apply.
) else (
    echo      Poppler already installed.
)

:: Step 6: Python packages
echo.
echo [6/6] Installing Python packages...
python -m pip install --upgrade ocrmypdf pytesseract Pillow pymupdf
if %errorlevel% neq 0 (
    echo      ERROR: Failed to install Python packages.
    pause & exit /b 1
)
echo      Python packages installed.

echo.
echo ============================================================
echo   Installation complete!
echo   Run the app with:  python app.py
echo.
echo   NOTE: If tools are not found, open a fresh terminal so
echo   PATH changes take effect.
echo ============================================================
echo.
pause
