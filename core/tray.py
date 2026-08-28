"""
tray.py - System tray icon, talking to Shell_NotifyIcon directly.

Replaces pystray, which is LGPL-3.0. Statically bundling an LGPL library into a
one-file build of a proprietary product triggers LGPL section 4 (the user must
be able to relink it), which is a compliance question nobody wants attached to
a consumer app. This is ctypes against Win32 APIs Windows already exposes, so
it adds no dependency and no licence obligation. It also drops Pillow from the
runtime: the icon is loaded from the shipped .ico rather than drawn at startup.

The whole module degrades to "no tray" rather than failing: create_tray() hands
back None on any non-Windows platform or any error, and main.py already treats
None as "tray unavailable" and keeps running.
"""

import sys
import threading

from core.logging_setup import get_logger

log = get_logger("tray")

_IS_WINDOWS = sys.platform == "win32"

# Message the shell posts back to us for mouse activity on the icon.
_WM_TRAYICON = 0x0400 + 1          # WM_APP + 1
_WM_DESTROY = 0x0002
_WM_COMMAND = 0x0111
_WM_LBUTTONDBLCLK = 0x0203
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONUP = 0x0205

_NIM_ADD = 0x0000
_NIM_MODIFY = 0x0001
_NIM_DELETE = 0x0002

_NIF_MESSAGE = 0x0001
_NIF_ICON = 0x0002
_NIF_TIP = 0x0004

_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x0010
_LR_DEFAULTSIZE = 0x0040

_IDI_APPLICATION = 32512

_MF_STRING = 0x0000
_MF_SEPARATOR = 0x0800
_TPM_RIGHTBUTTON = 0x0002
_TPM_RETURNCMD = 0x0100

_ID_SHOW = 1001
_ID_QUIT = 1002


def create_tray(on_show, on_quit, icon_path: str = "", tooltip: str = "FocusGuard"):
    """
    Build a tray icon, or return None if one cannot be created.

    `on_show` and `on_quit` are called from the tray's own thread, so a Tk
    caller must marshal back with root.after(). The returned object has run()
    and stop(), matching how main.py already drives the tray.
    """
    if not _IS_WINDOWS:
        return None
    try:
        return _WindowsTray(on_show, on_quit, icon_path, tooltip)
    except Exception as e:
        log.warning("Tray icon unavailable: %s", e)
        return None


class _WindowsTray:
    """A hidden message-only window that owns a notification-area icon."""

    def __init__(self, on_show, on_quit, icon_path: str, tooltip: str):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._on_show = on_show
        self._on_quit = on_quit
        self._tooltip = tooltip[:127]
        self._icon_path = icon_path
        self._hwnd = None
        self._added = False
        self._stopping = threading.Event()

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        self._build_structures()

    # ── Win32 plumbing ────────────────────────────────────────────────────────

    def _build_structures(self):
        ctypes = self._ctypes
        wintypes = self._wintypes

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
            ]

        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", ctypes.WINFUNCTYPE(
                    ctypes.c_long, wintypes.HWND, wintypes.UINT,
                    wintypes.WPARAM, wintypes.LPARAM)),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        self._NOTIFYICONDATA = NOTIFYICONDATA
        self._WNDCLASS = WNDCLASS
        self._WNDPROC = WNDCLASS._fields_[1][1]

    def _load_icon(self):
        """The shipped .ico, falling back to the stock application icon."""
        if self._icon_path:
            handle = self._user32.LoadImageW(
                None, self._icon_path, _IMAGE_ICON, 0, 0,
                _LR_LOADFROMFILE | _LR_DEFAULTSIZE,
            )
            if handle:
                return handle
            log.debug("Could not load icon from %s", self._icon_path)
        return self._user32.LoadIconW(None, self._ctypes.c_wchar_p(_IDI_APPLICATION))

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == _WM_TRAYICON:
                event = lparam & 0xFFFF
                if event in (_WM_LBUTTONUP, _WM_LBUTTONDBLCLK):
                    self._invoke(self._on_show)
                elif event == _WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            if msg == _WM_COMMAND:
                command = wparam & 0xFFFF
                if command == _ID_SHOW:
                    self._invoke(self._on_show)
                elif command == _ID_QUIT:
                    self._invoke(self._on_quit)
                return 0
            if msg == _WM_DESTROY:
                self._user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            log.error("Tray message handling failed: %s", e)
        return self._user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    @staticmethod
    def _invoke(callback):
        if callback:
            try:
                callback()
            except Exception as e:
                log.error("Tray callback failed: %s", e)

    def _show_menu(self, hwnd):
        menu = self._user32.CreatePopupMenu()
        if not menu:
            return
        try:
            self._user32.AppendMenuW(menu, _MF_STRING, _ID_SHOW, "Show FocusGuard")
            self._user32.AppendMenuW(menu, _MF_SEPARATOR, 0, None)
            self._user32.AppendMenuW(menu, _MF_STRING, _ID_QUIT, "Quit")

            pos = self._wintypes.POINT()
            self._user32.GetCursorPos(self._ctypes.byref(pos))
            # Required so the menu closes when the user clicks elsewhere.
            self._user32.SetForegroundWindow(hwnd)
            choice = self._user32.TrackPopupMenu(
                menu, _TPM_RIGHTBUTTON | _TPM_RETURNCMD,
                pos.x, pos.y, 0, hwnd, None,
            )
            if choice == _ID_SHOW:
                self._invoke(self._on_show)
            elif choice == _ID_QUIT:
                self._invoke(self._on_quit)
        finally:
            self._user32.DestroyMenu(menu)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Create the icon and pump messages. Blocks until stop() is called."""
        ctypes = self._ctypes
        wintypes = self._wintypes

        # Kept on self so the trampoline is not garbage-collected while Windows
        # still holds a pointer to it.
        self._proc_ref = self._WNDPROC(self._wnd_proc)

        wc = self._WNDCLASS()
        wc.lpfnWndProc = self._proc_ref
        wc.lpszClassName = "FocusGuardTrayWindow"
        wc.hInstance = self._kernel32.GetModuleHandleW(None)

        atom = self._user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            # A previous run in this process may have registered it already.
            log.debug("Tray window class already registered")

        self._hwnd = self._user32.CreateWindowExW(
            0, wc.lpszClassName, "FocusGuard", 0, 0, 0, 0, 0,
            None, None, wc.hInstance, None,
        )
        if not self._hwnd:
            raise OSError("could not create tray window")

        data = self._NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(self._NOTIFYICONDATA)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        data.uCallbackMessage = _WM_TRAYICON
        data.hIcon = self._load_icon()
        data.szTip = self._tooltip
        self._data = data

        if not self._shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data)):
            raise OSError("Shell_NotifyIcon failed")
        self._added = True
        log.debug("Tray icon created")

        msg = wintypes.MSG()
        while not self._stopping.is_set():
            result = self._user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):        # WM_QUIT, or an error
                break
            self._user32.TranslateMessage(ctypes.byref(msg))
            self._user32.DispatchMessageW(ctypes.byref(msg))

        self._remove_icon()

    def stop(self) -> None:
        """Remove the icon and end the message loop. Safe to call twice."""
        self._stopping.set()
        self._remove_icon()
        if self._hwnd:
            try:
                self._user32.PostMessageW(self._hwnd, _WM_DESTROY, 0, 0)
            except Exception:
                log.debug("Could not post tray shutdown message", exc_info=True)

    def _remove_icon(self) -> None:
        if not self._added:
            return
        try:
            self._shell32.Shell_NotifyIconW(_NIM_DELETE,
                                            self._ctypes.byref(self._data))
        except Exception as e:
            log.debug("Could not remove tray icon: %s", e)
        self._added = False
