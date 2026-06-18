@echo off
setlocal EnableDelayedExpansion
title Image to PDF Converter - Installer

echo ============================================================
echo   Image to PDF Converter - Windows Installer
echo ============================================================
echo.

:: Detect winget
where winget >nul 2>&1
if %errorlevel% equ 0 (
    set HAS_WINGET=1
    echo      winget detected - will use it when available.
) else (
    set HAS_WINGET=0
    echo      winget not detected - using direct downloads.
)
echo.

:: Helper: install via winget or direct fallback
:: Usage: call :install_tool "Display Name" "WingetId" "FallbackUrl" "FallbackArgs" "PathToAdd"
::   Args 1-5 are required.  Additional args are appended to fallback exe.
goto :main

:install_tool
set TOOL_NAME=%~1
set WINGET_ID=%~2
set FALLBACK_URL=%~3
set FALLBACK_ARGS=%~4
set PATH_ADD=%~5

if "!HAS_WINGET!"=="1" (
    echo      Installing !TOOL_NAME! via winget...
    winget install --id "!WINGET_ID!" --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! equ 0 (
        echo      !TOOL_NAME! installed via winget.
        if not "!PATH_ADD!"=="" set "PATH=!PATH!;!PATH_ADD!"
        exit /b 0
    )
    echo      winget failed. Falling back to direct download...
) else (
    echo      winget unavailable. Using direct download...
)

if "!FALLBACK_URL!"=="" (
    echo      ERROR: No fallback available for !TOOL_NAME!.
    echo      Please install manually.
    exit /b 1
)

curl -Lo "%TEMP%\!TOOL_NAME!_installer.exe" "!FALLBACK_URL!"
if !errorlevel! neq 0 (
    echo      ERROR: Could not download !TOOL_NAME!.
    exit /b 1
)

"%TEMP%\!TOOL_NAME!_installer.exe" !FALLBACK_ARGS!
if !errorlevel! neq 0 (
    echo      ERROR: Could not install !TOOL_NAME!.
    exit /b 1
)
if not "!PATH_ADD!"=="" set "PATH=!PATH!;!PATH_ADD!"
echo      !TOOL_NAME! installed.
exit /b 0

:main

:: Step 1: Python
echo [1/5] Checking for Python 3.9+...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    if "!HAS_WINGET!"=="1" (
        echo      Python not found. Installing via winget...
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        if !errorlevel! neq 0 (
            echo      ERROR: winget failed to install Python.
            echo      Please install Python 3.12+ from https://www.python.org/downloads/
            pause & exit /b 1
        )
        call refreshenv >nul 2>&1
        set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
        echo      Python installed successfully.
    ) else (
        echo      ERROR: Python not found and winget is not available.
        echo      Please install Python 3.12+ from https://www.python.org/downloads/
        echo      or from the Microsoft Store, then re-run this installer.
        pause & exit /b 1
    )
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo      Found Python !PY_VER!
)

:: Step 2: pip
echo.
echo [2/5] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo      Done.

:: Step 3: Tesseract
echo.
echo [3/5] Checking for Tesseract OCR...
tesseract --version >nul 2>&1
if %errorlevel% neq 0 (
    call :install_tool "Tesseract" "UB-Mannheim.TesseractOCR" ^
        "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe" ^
        "/S" ^
        "C:\Program Files\Tesseract-OCR"
    if !errorlevel! neq 0 (
        echo      ERROR: Could not install Tesseract automatically.
        echo      Please install from: https://github.com/UB-Mannheim/tesseract/wiki
        pause & exit /b 1
    )
    echo      Tesseract installed.
) else (
    echo      Tesseract already installed.
)

:: Step 4: Ghostscript
echo.
echo [4/5] Checking for Ghostscript...
gswin64c --version >nul 2>&1 || gswin32c --version >nul 2>&1
if %errorlevel% neq 0 (
    call :install_tool "Ghostscript" "ArtifexSoftware.GhostScript" ^
        "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10031/gs10031w64.exe" ^
        "/S" ^
        ""
    if !errorlevel! neq 0 (
        echo      ERROR: Could not install Ghostscript automatically.
        echo      Please install from: https://www.ghostscript.com/releases/gsdnld.html
        pause & exit /b 1
    )
    echo      Ghostscript installed.
) else (
    echo      Ghostscript already installed.
)

:: Step 5: Python packages
echo.
echo [5/5] Installing Python packages...
python -m pip install --upgrade ocrmypdf pytesseract Pillow pymupdf
if %errorlevel% neq 0 (
    echo      ERROR: Failed to install Python packages.
    pause & exit /b 1
)
echo      Python packages installed.

echo.
echo ============================================================
echo   Installation complete!
echo   Run the app with:  python ArkIndex.py
echo.
echo   NOTE: If tools are not found, open a fresh terminal so
echo   PATH changes take effect.
echo ============================================================
echo.
pause
