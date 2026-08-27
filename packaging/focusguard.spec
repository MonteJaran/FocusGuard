# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for FocusGuard.

Build with:   pyinstaller packaging/focusguard.spec --noconfirm
Run from the repository root, not from packaging/.

One-FOLDER, not one-file, deliberately:

  * One-file unpacks the whole app to %TEMP% on every launch, which is slow
    and is a behaviour antivirus heuristics score badly -- and this app already
    enumerates and closes processes, so it does not need more suspicion.
  * A folder build keeps every DLL a separate signable file. Signing a one-file
    stub leaves its payload unsigned.
  * Inno Setup wraps the folder into a single installer anyway, so the user
    still downloads exactly one file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(SPECPATH).parent))
from core.version import APP_NAME, __version__      # noqa: E402

ROOT = Path(SPECPATH).parent
ICON = ROOT / "FocusGuard.ico"

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Shipped so the tray can load the icon at runtime and the consent gate
        # can fall back to the bundled policy when the site is unreachable.
        (str(ICON), "."),
        (str(ROOT / "PRIVACY.md"), "."),
    ],
    hiddenimports=[
        # plyer resolves its platform backend by string at call time, so
        # PyInstaller's import graph cannot see this one.
        "plyer.platforms.win.notification",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Not used at runtime. Excluding them keeps the build small and avoids
        # shipping code we have not reviewed.
        "PIL", "pystray", "numpy", "pandas", "matplotlib",
        "pytest", "ruff", "setuptools", "pip",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX-packed binaries are a strong antivirus signal
    console=False,       # GUI app: no console window
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.is_file() else None,
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
