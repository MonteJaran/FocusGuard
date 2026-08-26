@echo off
setlocal enabledelayedexpansion
title FocusGuard
cd /d "%~dp0"
cls

:: ─────────────────────────────────────────────────────────────────────────────
::  Banner
:: ─────────────────────────────────────────────────────────────────────────────
powershell -NoProfile -Command ^
    "Write-Host ''; " ^
    "Write-Host '  ╔══════════════════════════════════════════╗' -ForegroundColor Cyan; " ^
    "Write-Host '  ║' -ForegroundColor Cyan -NoNewline; " ^
    "Write-Host '   F O C U S G U A R D' -ForegroundColor Yellow -NoNewline; " ^
    "Write-Host '                  ║' -ForegroundColor Cyan; " ^
    "Write-Host '  ║  App Usage Monitor and Limiter         ║' -ForegroundColor Cyan; " ^
    "Write-Host '  ╚══════════════════════════════════════════╝' -ForegroundColor Cyan; " ^
    "Write-Host '';"

:: ─────────────────────────────────────────────────────────────────────────────
::  Check Python
:: ─────────────────────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 goto :no_python

powershell -NoProfile -Command "Write-Host '  [OK] Python detected.' -ForegroundColor Green"
goto :deps

:: ─────────────────────────────────────────────────────────────────────────────
:no_python
:: ─────────────────────────────────────────────────────────────────────────────
powershell -NoProfile -Command ^
    "Write-Host '  ╔══════════════════════════════════════════╗' -ForegroundColor Red; " ^
    "Write-Host '  ║  Python is not installed on this PC.    ║' -ForegroundColor Red; " ^
    "Write-Host '  ║  FocusGuard requires Python 3.10+.      ║' -ForegroundColor Red; " ^
    "Write-Host '  ╚══════════════════════════════════════════╝' -ForegroundColor Red; " ^
    "Write-Host ''; " ^
    "Write-Host '  Press ENTER to download and install Python automatically.' -ForegroundColor Yellow; " ^
    "Write-Host '  (Official installer from python.org)' -ForegroundColor DarkGray; " ^
    "Write-Host '';"

pause >nul

powershell -NoProfile -Command ^
    "Write-Host '  Downloading Python 3.12 ...' -ForegroundColor Cyan; " ^
    "$url = 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe'; " ^
    "$out = \"$env:TEMP\python_installer.exe\"; " ^
    "try { Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing; " ^
    "  Write-Host '  Download complete. Launching installer...' -ForegroundColor Green; " ^
    "  Start-Process $out -Wait; " ^
    "  Write-Host ''; " ^
    "  Write-Host '  Done! Please close this window and run FocusGuard.bat again.' -ForegroundColor Green; " ^
    "} catch { Write-Host \"  ERROR: $($_.Exception.Message)\" -ForegroundColor Red; }; " ^
    "Write-Host ''; " ^
    "Write-Host '  Press any key to exit...' -ForegroundColor DarkGray;"

pause >nul
exit /b

:: ─────────────────────────────────────────────────────────────────────────────
:deps
:: ─────────────────────────────────────────────────────────────────────────────
powershell -NoProfile -Command "Write-Host '  Checking dependencies...' -ForegroundColor Cyan"
python -m pip install -r requirements.txt -q --exists-action i >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Write-Host '  Installing dependencies...' -ForegroundColor Yellow"
    python -m pip install -r requirements.txt -q
)
powershell -NoProfile -Command "Write-Host '  [OK] Dependencies ready.' -ForegroundColor Green"

:: ─────────────────────────────────────────────────────────────────────────────
::  Generate icon (once)
:: ─────────────────────────────────────────────────────────────────────────────
if not exist FocusGuard.ico (
    powershell -NoProfile -Command "Write-Host '  Building icon...' -ForegroundColor Cyan"
    python generate_icon.py
    powershell -NoProfile -Command "Write-Host '  [OK] Icon ready.' -ForegroundColor Green"
)

:: ─────────────────────────────────────────────────────────────────────────────
::  Create desktop shortcut (once)
:: ─────────────────────────────────────────────────────────────────────────────
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

:: ─────────────────────────────────────────────────────────────────────────────
::  Launch
:: ─────────────────────────────────────────────────────────────────────────────
powershell -NoProfile -Command ^
    "Write-Host ''; " ^
    "Write-Host '  Launching FocusGuard...' -ForegroundColor Green; " ^
    "Write-Host '';"
timeout /t 1 >nul
start "" pythonw main.py
