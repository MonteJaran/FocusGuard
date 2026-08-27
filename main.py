"""FocusGuard - Application Usage Tracker"""

import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

# Ensure we can import our modules regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import logging_setup, tray
from core.config import Config
from core.consent import has_consented, record_consent, show_consent_dialog
from core.database import Database
from core.monitor import Monitor
from core.logging_setup import get_logger
from core.version import __version__
from ui.app import MainApp

log = get_logger("main")


def enable_dpi_awareness() -> None:
    """
    Tell Windows this process scales its own UI.

    Without this, Tk is bitmap-stretched by the OS on any display above 100%
    scaling, which is most laptops -- the whole window renders blurry and
    undersized. Must be called before the first Tk window exists.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Per-monitor v2 where available (Windows 10 1703+), which also keeps
        # the UI sharp when the window moves between displays.
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
            return
        except Exception:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system-DPI aware
            return
        except Exception:
            pass
        ctypes.windll.user32.SetProcessDPIAware()            # Vista fallback
    except Exception:
        # Deliberate: every path above is a best-effort probe for an API that
        # may not exist on this Windows version. Blurry is survivable;
        # crashing before the window opens is not.
        pass


def create_tray_icon(root: tk.Tk, quit_fn):
    """
    Build the system tray icon, or None if one is unavailable.

    Uses core/tray.py (ctypes + Shell_NotifyIcon) rather than pystray, which is
    LGPL-3.0. Callbacks arrive on the tray thread, so both marshal back to the
    Tk main thread with root.after().
    """
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "FocusGuard.ico")

    def show_window():
        root.after(0, lambda: (root.deiconify(), root.lift(), root.focus_force()))

    def on_quit():
        root.after(0, quit_fn)

    return tray.create_tray(
        on_show=show_window,
        on_quit=on_quit,
        icon_path=icon_path if os.path.isfile(icon_path) else "",
        tooltip=f"FocusGuard {__version__} \u2014 Running",
    )


def main() -> None:
    # Before any Tk window exists, or the UI renders blurry on high-DPI screens.
    enable_dpi_awareness()

    # ── Core services ─────────────────────────────────────────────────────────
    try:
        db = Database()
        logging_setup.configure(db.data_dir)
    except Exception as exc:
        messagebox.showerror("FocusGuard \u2014 Database Error",
                             f"Could not initialise the database:\n{exc}")
        sys.exit(1)

    config = Config()

    # ── Tkinter root ──────────────────────────────────────────────────────────
    root = tk.Tk()

    # ── Privacy consent gate ──────────────────────────────────────────────────
    # Must run before the monitor starts: the monitor is what records usage, so
    # nothing may be recorded until the user has seen the policy and agreed.
    if not has_consented(config):
        root.withdraw()
        accepted = show_consent_dialog(root)
        record_consent(config, accepted)
        if not accepted:
            db.close()
            root.destroy()
            sys.exit(0)

    monitor = Monitor(db, config)
    monitor.start()

    app = MainApp(root, db, config, monitor)

    # ── Monitor → UI callbacks ─────────────────────────────────────────────────
    def on_monitor_event(event_type: str, data: dict) -> None:
        if event_type == "app_killed" and config.get("notifications_enabled", True):
            name      = data.get("name", "App")
            limit_min = data.get("limit_min", 0)
            # Must touch tkinter from the main thread only
            root.after(0, lambda n=name, lm=limit_min: app.show_kill_toast(n, lm))

    monitor.add_callback(on_monitor_event)

    tray_icon = [None]
    tray_started = [False]

    # ── Quit handler ──────────────────────────────────────────────────────────
    def do_quit() -> None:
        # Each step is independent: one failing must not strand the others and
        # leave the process alive, but it should still be recorded.
        for label, step in (("stop monitor", monitor.stop),
                            ("close database", db.close),
                            ("destroy window", root.destroy)):
            try:
                step()
            except Exception as e:
                log.error("Shutdown step '%s' failed: %s", label, e)

    app.quit_app = do_quit

    # ── Close → hide to tray ──────────────────────────────────────────────────
    def on_close() -> None:
        root.withdraw()
        if not tray_started[0] and tray_icon[0] is not None:
            tray_started[0] = True
            t = threading.Thread(target=tray_icon[0].run, daemon=True)
            t.start()

    icon = create_tray_icon(root, do_quit)
    tray_icon[0] = icon

    root.protocol("WM_DELETE_WINDOW", on_close)

    # ── First-run notice ──────────────────────────────────────────────────────
    if config.get("first_run", True):
        config.set("first_run", False)
        root.after(
            800,
            lambda: messagebox.showinfo(
                "Welcome to FocusGuard",
                "Welcome!\n\n"
                "Start by clicking 'Browse Pre-loaded Apps' on the Files tab to "
                "add applications you want to monitor.\n\n"
                "Closing this window will minimise FocusGuard to the system tray.",
                parent=root,
            ),
        )

    # ── Always show window on startup (reset any accidental hidden state) ──────
    config.set("start_minimized", False)
    root.deiconify()
    root.lift()
    root.focus_force()

    # ── Main loop ─────────────────────────────────────────────────────────────
    root.mainloop()

    # Cleanup after mainloop exits (e.g. OS-level close)
    for label, step in (("stop monitor", monitor.stop),
                        ("close database", db.close)):
        try:
            step()
        except Exception as e:
            log.error("Cleanup step '%s' failed: %s", label, e)

    if tray_icon[0] is not None:
        try:
            tray_icon[0].stop()
        except Exception as e:
            log.debug("Could not stop tray icon: %s", e)


if __name__ == '__main__':
    main()
