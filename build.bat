@echo off
title VAULT Build

echo.
echo ========================================
echo   VAULT - Build Script
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

python -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo Installing cryptography...
    pip install cryptography
)

echo Cleaning old build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist VAULT.spec del /q VAULT.spec

echo.
echo Building VAULT.exe ...
echo.

python -m PyInstaller --name "VAULT" --onefile --windowed --clean --noupx --hidden-import=cryptography --hidden-import=cryptography.hazmat.primitives.ciphers.aead --hidden-import=cryptography.hazmat.primitives.kdf.scrypt --hidden-import=cryptography.hazmat.primitives.kdf.hkdf --hidden-import=cryptography.hazmat.primitives.hashes --hidden-import=cryptography.hazmat.backends --hidden-import=cryptography.hazmat.backends.openssl --hidden-import=tkinter --hidden-import=tkinter.ttk --hidden-import=tkinter.messagebox --hidden-import=tkinter.filedialog --hidden-import=tkinter.simpledialog --collect-all cryptography main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo EXE created in dist\VAULT.exe
echo.
"C:\Users\rasheed\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
set INNO=""
if exist "C:\Users\rasheed\AppData\Local\Programs\Inno Setup 6\ISCC.exe" set INNO="C:\Users\rasheed\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Users\rasheed\AppData\Local\Programs\Inno Setup 6\ISCC.exe"       set INNO="C:\Users\rasheed\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

if %INNO%=="" (
    echo Inno Setup not found - skipping installer
    echo Download from: https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 0
)

echo Building installer...
%INNO% vault.iss

if errorlevel 1 (
    echo ERROR: Installer build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build complete!
echo   EXE:       dist\VAULT.exe
echo   Installer: Output\VAULT_Setup.exe
echo ========================================
echo.
pause
