"""
procutil.py - Closing applications without destroying the user's work.

The original implementation called psutil's `kill()`, which on Windows maps
straight to TerminateProcess: the application gets no shutdown message, no
chance to flush, and no save prompt. Every unsaved buffer is gone. For an app
that limits editors and creative tools, that is the single most damaging thing
it can do.

This module closes in stages, so terminating is a last resort rather than the
only resort:

    1. Post WM_CLOSE to the process's top-level windows. This is what clicking
       the X does, so the app runs its own save-and-exit path and can show its
       own "save changes?" prompt.
    2. Wait for it to exit on its own.
    3. terminate() the stragglers — still TerminateProcess on Windows, but only
       for processes that ignored a polite request.

Stage 1 is Windows-specific and done through ctypes, so no new dependency. On
any other platform it falls back to SIGTERM, which is the same idea.
"""

import sys
import time

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    _PSUTIL_AVAILABLE = False

from core.protected import is_protected

_IS_WINDOWS = sys.platform == "win32"

# How long to wait for an app to close itself after WM_CLOSE before escalating.
DEFAULT_CLOSE_TIMEOUT = 10.0


def find_matching_pids(exe_name: str = "", exe_path: str = "") -> list:
    """
    PIDs whose executable matches by name or by full path.

    Returns [] for anything protected, so a protected process can never be
    selected for closing even if it somehow got into the tracked list.
    """
    if not _PSUTIL_AVAILABLE:
        return []
    if is_protected(exe_name, exe_path):
        return []

    want_name = (exe_name or "").lower().strip()
    want_path = (exe_path or "").lower().replace("\\", "/").strip()
    if not want_name and not want_path:
        return []

    pids = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            pexe = (proc.info.get("exe") or "").lower().replace("\\", "/")
            # Never touch a protected process, whatever the tracked entry says.
            if is_protected(pname, pexe):
                continue
            if (want_name and pname == want_name) or (want_path and pexe == want_path):
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def request_close(pids) -> int:
    """
    Ask each process to close itself, the same way clicking the X does.

    On Windows this posts WM_CLOSE to every visible top-level window owned by
    the process. Elsewhere it sends SIGTERM. Returns how many processes were
    successfully asked.
    """
    if not pids:
        return 0
    if _IS_WINDOWS:
        return _post_wm_close(pids)
    return _send_sigterm(pids)


def _send_sigterm(pids) -> int:
    if not _PSUTIL_AVAILABLE:
        return 0
    asked = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            asked += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return asked


def _post_wm_close(pids) -> int:
    """Post WM_CLOSE to the top-level windows of the given processes."""
    import ctypes
    from ctypes import wintypes

    WM_CLOSE = 0x0010
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    wanted = set(pids)
    asked = set()

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in wanted and user32.IsWindowVisible(hwnd):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            asked.add(pid.value)
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(_callback), 0)
    except Exception:
        return 0
    return len(asked)


def wait_for_exit(pids, timeout: float) -> list:
    """Wait up to `timeout` seconds; return the PIDs still alive."""
    if not _PSUTIL_AVAILABLE or not pids:
        return []
    procs = []
    for pid in pids:
        try:
            procs.append(psutil.Process(pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not procs:
        return []
    _gone, alive = psutil.wait_procs(procs, timeout=timeout)
    return [p.pid for p in alive]


def force_terminate(pids) -> int:
    """Terminate processes that ignored WM_CLOSE. Returns how many were hit."""
    if not _PSUTIL_AVAILABLE or not pids:
        return 0
    killed = 0
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            if is_protected(proc.name()):
                continue
            proc.terminate()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed


def close_app(exe_name: str = "", exe_path: str = "",
              timeout: float = DEFAULT_CLOSE_TIMEOUT, log=None) -> dict:
    """
    Close every process matching this app, politely first.

    Returns a summary dict:
        {"matched": int, "asked": int, "forced": int, "closed": bool}

    `closed` is True if at least one process was matched and none survived.
    """
    def _log(msg):
        if log:
            log(msg)

    pids = find_matching_pids(exe_name, exe_path)
    if not pids:
        if is_protected(exe_name, exe_path):
            _log(f"Refusing to close protected process: {exe_name or exe_path}")
        return {"matched": 0, "asked": 0, "forced": 0, "closed": False}

    asked = request_close(pids)
    _log(f"Asked {asked}/{len(pids)} process(es) of '{exe_name}' to close.")

    still_alive = wait_for_exit(pids, timeout)

    forced = 0
    if still_alive:
        _log(f"{len(still_alive)} process(es) ignored the close request — terminating.")
        forced = force_terminate(still_alive)
        # Give the OS a moment to reap them before reporting.
        time.sleep(0.2)
        still_alive = wait_for_exit(still_alive, 2.0)

    return {
        "matched": len(pids),
        "asked": asked,
        "forced": forced,
        "closed": not still_alive,
    }
