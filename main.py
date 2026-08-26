"""FocusGuard - Application Usage Tracker"""

import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

# Ensure we can import our modules regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import Database
from core.config import Config
from core.consent import has_consented, record_consent, show_consent_dialog
from core.monitor import Monitor
from ui.app import MainApp


def create_tray_icon(root: tk.Tk, quit_fn):
    """
    Create and return a pystray system tray icon, or None if pystray/Pillow
    are not available.
    """
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Draw a simple clock-like icon
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Outer ring
        d.ellipse([0, 0, 63, 63], fill='#1a1a2e')
        d.ellipse([0, 0, 63, 63], outline='#e94560', width=4)
        # Inner circle
        d.ellipse([8, 8, 55, 55], fill='#0f3460')
        # Clock hands
        d.line([32, 32, 32, 14], fill='#e94560', width=4)
        d.line([32, 32, 46, 38], fill='#e0e0e0', width=3)
        # Centre dot
        d.ellipse([28, 28, 36, 36], fill='#e0e0e0')

        def show_window(icon, item):
            root.after(0, lambda: (root.deiconify(), root.lift(), root.focus_force()))

        def on_quit(icon, item):
            icon.stop()
            root.after(0, quit_fn)

        menu = pystray.Menu(
            pystray.MenuItem('Show FocusGuard', show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', on_quit),
        )
        icon = pystray.Icon('FocusGuard', img, 'FocusGuard \u2014 Running', menu)
        return icon

    except Exception:
        return None


def main() -> None:
    # ── Core services ─────────────────────────────────────────────────────────
    try:
        db = Database()
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
        try:
            monitor.stop()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

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
    try:
        monitor.stop()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass


if __name__ == '__main__':
    main()
