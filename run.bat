@echo off
cd /d "%~dp0"
start "" pythonw main.py
echo FocusGuard is starting in the background.
echo You can close this window safely.
timeout /t 3 >nul
