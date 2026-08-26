"""
settings_page.py - Settings tab for FocusGuard.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# ── Color Scheme ─────────────────────────────────────────────────────────────
BG      = '#1a1a2e'
BG2     = '#16213e'
BG3     = '#0f3460'
ACCENT  = '#e94560'
TEXT    = '#e0e0e0'
TEXT2   = '#9090a0'
SUCCESS = '#4ade80'
WARNING = '#fbbf24'
ERROR   = '#f87171'

_APP_VERSION = "1.0.0"


class SettingsPage(ttk.Frame):
    def __init__(self, parent, db, config, monitor) -> None:
        super().__init__(parent)
        self.db = db
        self.config = config
        self.monitor = monitor
        self.configure(style='TFrame')
        self._build_ui()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Outer scrollable canvas
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Inner frame
        inner = ttk.Frame(canvas, style='TFrame')
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_resize(event):
            canvas.itemconfig(window_id, width=event.width)

        inner.bind('<Configure>', _on_configure)
        canvas.bind('<Configure>', _on_canvas_resize)

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        canvas.bind_all('<MouseWheel>', _on_mousewheel)

        self._inner = inner

        # ── Sections ──────────────────────────────────────────────────────────
        self._build_monitoring_section(inner)
        self._separator(inner)
        self._build_notifications_section(inner)
        self._separator(inner)
        self._build_enforcement_section(inner)
        self._separator(inner)
        self._build_startup_section(inner)
        self._separator(inner)
        self._build_data_section(inner)
        self._separator(inner)
        self._build_about_section(inner)

    def _separator(self, parent) -> None:
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=24, pady=4)

    def _section_header(self, parent, title: str) -> None:
        tk.Label(parent, text=title, bg=BG, fg=ACCENT,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=24, pady=(14, 4))

    # ── Section: Monitoring ───────────────────────────────────────────────────

    def _build_monitoring_section(self, parent) -> None:
        self._section_header(parent, "Monitoring")

        tk.Label(parent, text="Poll Interval", bg=BG, fg=TEXT,
                 font=('Segoe UI', 10)).pack(anchor='w', padx=32, pady=(0, 4))
        tk.Label(parent,
                 text="How often FocusGuard checks which apps are running.",
                 bg=BG, fg=TEXT2, font=('Segoe UI', 9)).pack(anchor='w', padx=32, pady=(0, 6))

        row = ttk.Frame(parent, style='TFrame')
        row.pack(anchor='w', padx=32, pady=(0, 6))

        interval_options = [
            ("15 seconds",  15),
            ("30 seconds",  30),
            ("1 minute",    60),
            ("2 minutes",  120),
            ("3 minutes",  180),
            ("5 minutes",  300),
        ]
        self._interval_var = tk.IntVar(value=self.config.get("poll_interval", 60))

        for label, value in interval_options:
            rb = ttk.Radiobutton(
                row, text=label,
                variable=self._interval_var, value=value,
                command=self._save_interval,
            )
            rb.pack(side='left', padx=(0, 12))

    def _save_interval(self) -> None:
        self.config.set("poll_interval", self._interval_var.get())

    # ── Section: Notifications ────────────────────────────────────────────────

    def _build_notifications_section(self, parent) -> None:
        self._section_header(parent, "Notifications")

        self._notif_var = tk.BooleanVar(value=self.config.get("notifications_enabled", True))
        ttk.Checkbutton(
            parent,
            text="Enable notifications when time limits are reached",
            variable=self._notif_var,
            command=lambda: self.config.set("notifications_enabled", self._notif_var.get()),
        ).pack(anchor='w', padx=32, pady=(0, 6))

        self._sound_var = tk.BooleanVar(value=self.config.get("notification_sound", False))
        ttk.Checkbutton(
            parent,
            text="Play sound with notifications",
            variable=self._sound_var,
            command=lambda: self.config.set("notification_sound", self._sound_var.get()),
        ).pack(anchor='w', padx=32, pady=(0, 6))

        warn_row = ttk.Frame(parent, style='TFrame')
        warn_row.pack(anchor='w', padx=32, pady=(0, 6))

        tk.Label(warn_row, text="Warn at", bg=BG, fg=TEXT,
                 font=('Segoe UI', 10)).pack(side='left')

        self._warn_var = tk.IntVar(value=self.config.get("warn_at_percent", 80))
        spin = ttk.Spinbox(warn_row, from_=10, to=100, increment=5,
                           textvariable=self._warn_var, width=6,
                           command=lambda: self.config.set("warn_at_percent", self._warn_var.get()))
        spin.pack(side='left', padx=(6, 4))
        spin.bind('<FocusOut>', lambda e: self.config.set("warn_at_percent", self._warn_var.get()))

        tk.Label(warn_row, text="% of daily limit",
                 bg=BG, fg=TEXT, font=('Segoe UI', 10)).pack(side='left')

    # ── Section: Enforcement ──────────────────────────────────────────────────

    def _build_enforcement_section(self, parent) -> None:
        self._section_header(parent, "Limit Enforcement")

        self._kill_var = tk.BooleanVar(
            value=self.config.get("auto_kill_over_limit", False))

        ttk.Checkbutton(
            parent,
            text="Automatically close apps that exceed their daily limit",
            variable=self._kill_var,
            command=lambda: self.config.set("auto_kill_over_limit", self._kill_var.get()),
        ).pack(anchor='w', padx=32, pady=(0, 4))

        tk.Label(
            parent,
            text=(
                "When enabled, FocusGuard will force-close any tracked app the moment its\n"
                "daily time limit is reached. It will also block the app from opening again\n"
                "if you have already used up your limit for the day."
            ),
            bg=BG, fg=TEXT2, font=('Segoe UI', 9), justify='left',
        ).pack(anchor='w', padx=48, pady=(0, 8))

    # ── Section: Startup ──────────────────────────────────────────────────────

    def _build_startup_section(self, parent) -> None:
        self._section_header(parent, "Startup")

        self._minimized_var = tk.BooleanVar(value=self.config.get("start_minimized", False))
        ttk.Checkbutton(
            parent,
            text="Start minimized to system tray",
            variable=self._minimized_var,
            command=lambda: self.config.set("start_minimized", self._minimized_var.get()),
        ).pack(anchor='w', padx=32, pady=(0, 8))

        startup_row = ttk.Frame(parent, style='TFrame')
        startup_row.pack(anchor='w', padx=32, pady=(0, 4))

        ttk.Button(startup_row, text="Add to Windows Startup",
                   command=self._add_to_startup).pack(side='left', padx=(0, 8))
        ttk.Button(startup_row, text="Remove from Windows Startup",
                   command=self._remove_from_startup).pack(side='left')

        self._startup_status_var = tk.StringVar()
        tk.Label(parent, textvariable=self._startup_status_var,
                 bg=BG, fg=TEXT2, font=('Segoe UI', 9)).pack(anchor='w', padx=32, pady=(2, 0))
        self._refresh_startup_status()

    def _refresh_startup_status(self) -> None:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ,
            )
            try:
                winreg.QueryValueEx(key, "FocusGuard")
                self._startup_status_var.set("Status: Added to Windows Startup")
            except FileNotFoundError:
                self._startup_status_var.set("Status: Not in Windows Startup")
            finally:
                winreg.CloseKey(key)
        except Exception:
            self._startup_status_var.set("Status: Unable to check registry")

    def _add_to_startup(self) -> None:
        try:
            import winreg
            # Determine the path to main.py and pythonw
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            main_py = os.path.join(app_dir, "main.py")
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.isfile(pythonw):
                pythonw = sys.executable  # fallback

            cmd = f'"{pythonw}" "{main_py}"'
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "FocusGuard", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            self._refresh_startup_status()
            messagebox.showinfo("Startup",
                                "FocusGuard has been added to Windows startup.",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Error",
                                 f"Could not add to startup:\n{exc}",
                                 parent=self)

    def _remove_from_startup(self) -> None:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, "FocusGuard")
                messagebox.showinfo("Startup",
                                    "FocusGuard has been removed from Windows startup.",
                                    parent=self)
            except FileNotFoundError:
                messagebox.showinfo("Startup",
                                    "FocusGuard was not in Windows startup.",
                                    parent=self)
            finally:
                winreg.CloseKey(key)
            self._refresh_startup_status()
        except Exception as exc:
            messagebox.showerror("Error",
                                 f"Could not remove from startup:\n{exc}",
                                 parent=self)

    # ── Section: Data Management ──────────────────────────────────────────────

    def _build_data_section(self, parent) -> None:
        self._section_header(parent, "Data Management")

        data_dir = self.db.data_dir
        tk.Label(parent, text=f"Data folder: {data_dir}",
                 bg=BG, fg=TEXT2, font=('Segoe UI', 9)).pack(anchor='w', padx=32, pady=(0, 6))

        btn_row = ttk.Frame(parent, style='TFrame')
        btn_row.pack(anchor='w', padx=32, pady=(0, 6))

        ttk.Button(btn_row, text="Open Data Folder",
                   command=lambda: self._open_data_folder(data_dir)).pack(side='left', padx=(0, 8))
        ttk.Button(btn_row, text="Clear All Usage Data",
                   command=self._clear_all_data, style='Danger.TButton').pack(side='left')

        tk.Label(parent,
                 text="Data is stored locally on this computer. No personal information is collected.",
                 bg=BG, fg=TEXT2, font=('Segoe UI', 9), wraplength=580, justify='left',
                 ).pack(anchor='w', padx=32, pady=(2, 6))

    def _open_data_folder(self, path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
            subprocess.Popen(f'explorer "{os.path.normpath(path)}"')
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _clear_all_data(self) -> None:
        # Require the user to type "DELETE"
        dialog = tk.Toplevel(self)
        dialog.title("Confirm Data Deletion")
        dialog.geometry("380x200")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog,
                 text="This will permanently delete ALL usage history.\nThis action cannot be undone.",
                 bg=BG, fg=WARNING, font=('Segoe UI', 10),
                 justify='center').pack(padx=20, pady=(18, 8))

        tk.Label(dialog, text='Type DELETE to confirm:',
                 bg=BG, fg=TEXT, font=('Segoe UI', 10)).pack(padx=20, pady=(0, 4), anchor='w')

        confirm_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=confirm_var, width=20)
        entry.pack(padx=20, pady=(0, 4), anchor='w')
        entry.focus_set()

        status_var = tk.StringVar()
        tk.Label(dialog, textvariable=status_var,
                 bg=BG, fg=ERROR, font=('Segoe UI', 9)).pack(padx=20, anchor='w')

        def do_delete() -> None:
            if confirm_var.get().strip() != "DELETE":
                status_var.set("You must type DELETE (all caps) to confirm.")
                return
            try:
                self.db.delete_all_data()
                dialog.destroy()
                messagebox.showinfo("Done", "All usage data has been deleted.", parent=self)
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=self)

        btn_row = ttk.Frame(dialog, style='TFrame')
        btn_row.pack(fill='x', padx=20, pady=(6, 12))
        ttk.Button(btn_row, text="Delete All Data",
                   command=do_delete, style='Danger.TButton').pack(side='right', padx=(6, 0))
        ttk.Button(btn_row, text="Cancel",
                   command=dialog.destroy).pack(side='right')

    # ── Section: About ────────────────────────────────────────────────────────

    def _build_about_section(self, parent) -> None:
        self._section_header(parent, "About FocusGuard")

        info_frame = tk.Frame(parent, bg=BG2, bd=0)
        info_frame.pack(fill='x', padx=24, pady=(4, 16))

        tk.Label(info_frame, text="FocusGuard",
                 bg=BG2, fg=ACCENT, font=('Segoe UI', 16, 'bold'),
                 ).pack(anchor='w', padx=16, pady=(12, 0))
        tk.Label(info_frame, text=f"Version {_APP_VERSION}",
                 bg=BG2, fg=TEXT2, font=('Segoe UI', 10),
                 ).pack(anchor='w', padx=16, pady=(0, 6))
        tk.Label(info_frame,
                 text=(
                     "FocusGuard is a lightweight Windows desktop application that monitors "
                     "your application usage in the background. Track how much time you spend "
                     "in your favourite apps, set daily and weekly limits, and receive "
                     "notifications when you are approaching or exceeding those limits."
                 ),
                 bg=BG2, fg=TEXT, font=('Segoe UI', 10),
                 wraplength=580, justify='left',
                 ).pack(anchor='w', padx=16, pady=(0, 8))

        tk.Label(info_frame,
                 text="Built with Python + tkinter  |  psutil  |  pystray  |  Pillow  |  plyer",
                 bg=BG2, fg=TEXT2, font=('Segoe UI', 9),
                 ).pack(anchor='w', padx=16, pady=(0, 12))
