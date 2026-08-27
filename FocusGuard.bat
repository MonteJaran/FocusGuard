@echo off
setlocal
title FocusGuard
cd /d "%~dp0"

:: ─────────────────────────────────────────────────────────────────────────────
::  Run FocusGuard from source, in its own virtual environment.
::
::  This is the DEVELOPER / source path. End users should get the installer
::  built by packaging\build.ps1 -- see BUILD.md.
::
::  Three things this deliberately does NOT do, all of which the previous
::  version did (AUDIT ST-01, ST-03):
::
::    * install packages into the user's GLOBAL Python. That silently upgrades
::      or downgrades libraries other projects depend on, and the user blames
::      whichever of their tools breaks first.
::    * download and execute a Python installer from the internet with no
::      checksum. Scored heavily by antivirus heuristics, and rightly.
::    * run PowerShell with -ExecutionPolicy Bypass. Same reason.
:: ─────────────────────────────────────────────────────────────────────────────

echo.
echo   FocusGuard - App Usage Monitor
echo   -----------------------------
echo.

:: ── Python ───────────────────────────────────────────────────────────────────
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 goto :no_python
    set "PY=python"
)

:: ── Virtual environment ──────────────────────────────────────────────────────
if not exist ".venv\Scripts\pythonw.exe" (
    echo   Creating a virtual environment in .venv ...
    %PY% -m venv .venv
    if %errorlevel% neq 0 goto :venv_failed
    echo   [OK] Created.
    echo.
    echo   Installing dependencies ...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if %errorlevel% neq 0 goto :deps_failed
    echo   [OK] Dependencies installed.
    echo.
)

:: ── Desktop shortcut, best effort ────────────────────────────────────────────
if exist "create_shortcut.ps1" (
    powershell -NoProfile -File "create_shortcut.ps1"
)

:: ── Launch ───────────────────────────────────────────────────────────────────
echo   Starting FocusGuard ...
start "" ".venv\Scripts\pythonw.exe" main.py
if %errorlevel% neq 0 goto :launch_failed

echo   [OK] Running. Look for the icon in your system tray.
timeout /t 3 >nul
exit /b 0

:: ─────────────────────────────────────────────────────────────────────────────
:no_python
echo   Python 3.10 or newer is required, and was not found.
echo.
echo   Install it from https://www.python.org/downloads/
echo   Tick "Add python.exe to PATH" during setup, then run this file again.
echo.
pause
exit /b 1

:venv_failed
echo   [ERROR] Could not create the virtual environment.
echo   Check that your Python install includes the "venv" module.
echo.
pause
exit /b 1

:deps_failed
echo   [ERROR] Could not install dependencies.
echo   The error above has the detail. Check your internet connection.
echo.
pause
exit /b 1

:launch_failed
echo   [ERROR] FocusGuard did not start.
echo   Run this to see the error:
echo       .venv\Scripts\python.exe main.py
echo.
pause
exit /b 1
