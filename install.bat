@echo off
cd /d "%~dp0"
echo ============================================
echo  FocusGuard - Installing dependencies...
echo ============================================
echo.

python -m pip install --upgrade pip
echo.
echo Installing required packages...
python -m pip install psutil pystray Pillow plyer
echo.

echo ============================================
echo  Verifying installation...
echo ============================================
python -c "import psutil; print('[OK] psutil', psutil.__version__)"
python -c "import pystray; print('[OK] pystray')"
python -c "from PIL import Image; print('[OK] Pillow')"
python -c "import plyer; print('[OK] plyer')"
echo.
echo ============================================
echo  Done! Close this window and run run.bat
echo ============================================
pause
