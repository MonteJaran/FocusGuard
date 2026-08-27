"""
files_page.py - Files tab for FocusGuard.
Shows all tracked apps with their paths and running status.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.apps_list import DEFAULT_APPS, APP_CATEGORIES, find_app_path, find_main_exe_in_folder
from core.protected import is_protected, protection_reason

# ── Color Scheme (mirrors app.py) ────────────────────────────────────────────
BG      = '#1a1a2e'
BG2     = '#16213e'
BG3     = '#0f3460'
ACCENT  = '#e94560'
TEXT    = '#e0e0e0'
TEXT2   = '#9090a0'
SUCCESS = '#4ade80'
WARNING = '#fbbf24'
ERROR   = '#f87171'


class FilesPage(ttk.Frame):
    def __init__(self, parent, db, config, monitor) -> None:
        super().__init__(parent)
        self.db = db
        self.config = config
        self.monitor = monitor
        self.configure(style='TFrame')
        self._build_ui()
        self.refresh()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = ttk.Frame(self, style='TFrame')
        toolbar.pack(fill='x', padx=12, pady=(10, 4))

        ttk.Button(toolbar, text="Browse Pre-loaded Apps",
                   command=self.browse_preloaded_apps, style='Accent.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text="Add Executable",
                   command=self.add_file).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text="Add Folder",
                   command=self.add_folder).pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text="Remove Selected",
                   command=self.remove_selected, style='Danger.TButton').pack(side='left', padx=(0, 6))
        ttk.Button(toolbar, text=">> Scan Now",
                   command=self._scan_now).pack(side='left', padx=(0, 6))

        # Search bar on the right
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', lambda *_: self.refresh())
        search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=20)
        search_entry.pack(side='right', padx=(0, 4))
        ttk.Label(toolbar, text="Filter:").pack(side='right', padx=(0, 2))

        # ── Treeview ─────────────────────────────────────────────────────────
        tree_frame = ttk.Frame(self, style='TFrame')
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(4, 4))

        cols = ("Name", "Category", "Executable", "Folder Path", "Status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse')

        self._tree.heading("Name",        text="Name",        anchor='w')
        self._tree.heading("Category",    text="Category",    anchor='w')
        self._tree.heading("Executable",  text="Executable",  anchor='w')
        self._tree.heading("Folder Path", text="Folder Path", anchor='w')
        self._tree.heading("Status",      text="Status",      anchor='center')

        self._tree.column("Name",        width=180, minwidth=120, anchor='w')
        self._tree.column("Category",    width=110, minwidth=80,  anchor='w')
        self._tree.column("Executable",  width=160, minwidth=110, anchor='w')
        self._tree.column("Folder Path", width=300, minwidth=150, anchor='w')
        self._tree.column("Status",      width=100, minwidth=80,  anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical',   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self._tree.pack(fill='both', expand=True)

        # Tag colours for status
        self._tree.tag_configure('running', foreground=ACCENT)
        self._tree.tag_configure('found',   foreground=SUCCESS)
        self._tree.tag_configure('missing', foreground=ERROR)

        # Double-click to edit
        self._tree.bind('<Double-1>', lambda e: self._edit_selected())

        # ── Info bar ─────────────────────────────────────────────────────────
        info_bar = tk.Frame(self, bg=BG3, height=28)
        info_bar.pack(fill='x', side='bottom')
        info_bar.pack_propagate(False)

        self._info_var = tk.StringVar(value="")
        tk.Label(info_bar, textvariable=self._info_var,
                 bg=BG3, fg=TEXT2, font=('Segoe UI', 9), anchor='w', padx=12
                 ).pack(side='left', fill='y')

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        search = self._search_var.get().lower().strip() if hasattr(self, '_search_var') else ""
        running_ids = self.monitor.running_apps.copy()

        # Remember selection
        selected_iid = self._tree.focus() if hasattr(self, '_tree') else None
        selected_app_id = None
        if selected_iid:
            vals = self._tree.item(selected_iid, 'values')
            if vals:
                # We store app_id in a hidden dict
                selected_app_id = self._iid_to_app_id.get(selected_iid)

        self._tree.delete(*self._tree.get_children())
        self._iid_to_app_id = {}

        try:
            apps = self.db.get_all_tracked_apps()
        except Exception:
            apps = []

        running_count = 0
        restore_iid = None

        for app in apps:
            name = app.get("name", "")
            if search and search not in name.lower() and search not in (app.get("category") or "").lower():
                continue

            app_id    = app["id"]
            category  = app.get("category") or "Custom"
            exe_name  = app.get("exe_name") or ""
            exe_path  = app.get("exe_path") or ""
            root_fold = app.get("root_folder") or ""

            is_running = app_id in running_ids
            exe_exists = exe_path and os.path.isfile(exe_path)

            if is_running:
                status = "\u25b6 Running"
                tag = 'running'
                running_count += 1
            elif exe_exists:
                status = "\u2705 Found"
                tag = 'found'
            else:
                status = "\u274c Not Found"
                tag = 'missing'

            iid = self._tree.insert(
                "", 'end',
                values=(name, category, exe_name, root_fold, status),
                tags=(tag,),
            )
            self._iid_to_app_id[iid] = app_id

            if selected_app_id and app_id == selected_app_id:
                restore_iid = iid

        if restore_iid:
            self._tree.focus(restore_iid)
            self._tree.selection_set(restore_iid)

        total = len(apps)
        self._info_var.set(f"{total} app(s) tracked  |  {running_count} currently running")

    # ── Toolbar Actions ───────────────────────────────────────────────────────

    def _scan_now(self) -> None:
        """Trigger an immediate process scan and refresh the view."""
        self.monitor.trigger_poll()
        # Refresh after a short delay to let the monitor thread finish
        self.after(500, self.refresh)

    def browse_preloaded_apps(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Browse Pre-loaded Apps")
        dialog.geometry("820x560")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()

        # ── Filter bar ───────────────────────────────────────────────────────
        filter_frame = ttk.Frame(dialog, style='TFrame')
        filter_frame.pack(fill='x', padx=12, pady=(10, 4))

        ttk.Label(filter_frame, text="Search:").pack(side='left')
        search_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=search_var, width=24).pack(side='left', padx=(4, 12))

        ttk.Label(filter_frame, text="Category:").pack(side='left')
        cat_var = tk.StringVar(value="All")
        cat_combo = ttk.Combobox(filter_frame, textvariable=cat_var, state='readonly', width=16,
                                 values=["All"] + APP_CATEGORIES)
        cat_combo.pack(side='left', padx=(4, 0))

        # ── Treeview ─────────────────────────────────────────────────────────
        cols = ("Name", "Category", "Install Path", "Found?")
        tree = ttk.Treeview(dialog, columns=cols, show='headings', selectmode='extended')
        tree.heading("Name",         text="Name",         anchor='w')
        tree.heading("Category",     text="Category",     anchor='w')
        tree.heading("Install Path", text="Install Path", anchor='w')
        tree.heading("Found?",       text="Found?",       anchor='center')

        tree.column("Name",         width=180, minwidth=130, anchor='w')
        tree.column("Category",     width=110, minwidth=80,  anchor='w')
        tree.column("Install Path", width=340, minwidth=160, anchor='w')
        tree.column("Found?",       width=80,  minwidth=60,  anchor='center')

        tree.tag_configure('found',   foreground=SUCCESS)
        tree.tag_configure('missing', foreground=TEXT2)

        vsb = ttk.Scrollbar(dialog, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y', padx=(0, 12))
        tree.pack(fill='both', expand=True, padx=(12, 0), pady=(4, 4))

        # ── Pre-compute path info ─────────────────────────────────────────────
        already_tracked = {
            (a.get("exe_name") or "").lower()
            for a in (self.db.get_all_tracked_apps() or [])
        }
        app_info = []
        for app in DEFAULT_APPS:
            result = find_app_path(app)
            app_info.append({
                "app":    app,
                "result": result,
                "found":  result is not None,
            })

        def _populate(search: str = "", category: str = "All") -> None:
            tree.delete(*tree.get_children())
            for info in app_info:
                app = info["app"]
                if category != "All" and app["category"] != category:
                    continue
                if search and search.lower() not in app["name"].lower():
                    continue
                result = info["result"]
                path_str = result["root"] if result else (app["root_folder_hints"][0] if app["root_folder_hints"] else "")
                found_str = "\u2705 Yes" if info["found"] else "\u274c No"
                tag = 'found' if info["found"] else 'missing'
                tree.insert("", 'end',
                            values=(app["name"], app["category"], path_str, found_str),
                            tags=(tag,))

        _populate()

        def _on_filter(*_):
            _populate(search_var.get(), cat_var.get())

        search_var.trace_add('write', _on_filter)
        cat_combo.bind('<<ComboboxSelected>>', _on_filter)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(dialog, style='TFrame')
        btn_frame.pack(fill='x', padx=12, pady=(4, 10))

        status_var = tk.StringVar()
        tk.Label(btn_frame, textvariable=status_var, bg=BG, fg=TEXT2,
                 font=('Segoe UI', 9)).pack(side='left')

        def add_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("No Selection", "Please select one or more apps to add.", parent=dialog)
                return
            added = 0
            skipped = 0
            for iid in selected:
                vals = tree.item(iid, 'values')
                app_name = vals[0]
                # Find matching app
                match = next((a for a in DEFAULT_APPS if a["name"] == app_name), None)
                if not match:
                    continue
                exe_lower = (match.get("exe_name") or "").lower()
                if exe_lower in already_tracked:
                    skipped += 1
                    continue
                result = find_app_path(match)
                exe_path  = result["exe"]  if result else ""
                root_fold = result["root"] if result else ""
                self.db.add_tracked_app(
                    name=match["name"],
                    exe_name=match.get("exe_name", ""),
                    exe_path=exe_path,
                    root_folder=root_fold,
                    category=match.get("category", "Custom"),
                )
                already_tracked.add(exe_lower)
                added += 1
            self.refresh()
            parts = []
            if added:
                parts.append(f"{added} app(s) added")
            if skipped:
                parts.append(f"{skipped} already tracked")
            status_var.set(", ".join(parts) + ".")

        ttk.Button(btn_frame, text="Add Selected", command=add_selected,
                   style='Accent.TButton').pack(side='right', padx=(6, 0))
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side='right')

    def _reject_if_protected(self, exe_name: str, exe_path: str = "") -> bool:
        """
        Refuse to track a protected process, explaining why.

        Without this the user can add a core Windows binary and give it a
        daily limit, and FocusGuard would then close it. See core/protected.py.
        """
        if not is_protected(exe_name, exe_path):
            return False
        messagebox.showwarning(
            "Cannot Track This Program",
            f"{exe_name} cannot be tracked.\n\n"
            f"{protection_reason(exe_name, exe_path)}",
            parent=self,
        )
        return True

    def add_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select an Executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        path = os.path.normpath(path)
        exe_name = os.path.basename(path)
        if self._reject_if_protected(exe_name, path):
            return
        root_folder = os.path.dirname(path)
        name = os.path.splitext(exe_name)[0].replace("_", " ").replace("-", " ").title()

        # Ask for a name
        name = _ask_string(self, "App Name", f"Enter a display name for '{exe_name}':", default=name)
        if name is None:
            return

        self.db.add_tracked_app(
            name=name,
            exe_name=exe_name,
            exe_path=path,
            root_folder=root_folder,
            category="Custom",
        )
        self.refresh()

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select an Application Folder", parent=self)
        if not folder:
            return
        folder = os.path.normpath(folder)
        exe_path = find_main_exe_in_folder(folder)
        if not exe_path:
            messagebox.showwarning(
                "No Executable Found",
                f"Could not find a main executable in:\n{folder}\n\n"
                "Try using 'Add Executable' to select it manually.",
                parent=self,
            )
            return
        exe_name = os.path.basename(exe_path)
        if self._reject_if_protected(exe_name, exe_path):
            return
        folder_name = os.path.basename(folder)
        name = folder_name.replace("_", " ").replace("-", " ").title()

        confirm = messagebox.askyesno(
            "Confirm",
            f"Detected executable:\n{exe_path}\n\nAdd '{name}' to tracking?",
            parent=self,
        )
        if not confirm:
            return

        name = _ask_string(self, "App Name", "Enter a display name:", default=name)
        if name is None:
            return

        self.db.add_tracked_app(
            name=name,
            exe_name=exe_name,
            exe_path=exe_path,
            root_folder=folder,
            category="Custom",
        )
        self.refresh()

    def remove_selected(self) -> None:
        iid = self._tree.focus()
        if not iid:
            messagebox.showinfo("No Selection", "Please select an app to remove.", parent=self)
            return
        app_id = self._iid_to_app_id.get(iid)
        if app_id is None:
            return
        vals = self._tree.item(iid, 'values')
        name = vals[0] if vals else "this app"
        if messagebox.askyesno("Confirm Remove",
                               f"Remove '{name}' from tracking?\n\nAll usage data will also be deleted.",
                               parent=self):
            self.db.remove_tracked_app(app_id)
            self.refresh()

    # ── Edit Dialog ───────────────────────────────────────────────────────────

    def _edit_selected(self) -> None:
        iid = self._tree.focus()
        if not iid:
            return
        app_id = self._iid_to_app_id.get(iid)
        if app_id is None:
            return

        apps = self.db.get_all_tracked_apps()
        app = next((a for a in apps if a["id"] == app_id), None)
        if not app:
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"Edit — {app['name']}")
        dialog.geometry("520x520")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        def _lbl(parent, text: str, row: int) -> None:
            tk.Label(parent, text=text, bg=BG, fg=TEXT2,
                     font=('Segoe UI', 9), anchor='w').grid(
                row=row, column=0, sticky='w', padx=(16, 8), pady=(8, 0))

        def _ent(parent, row: int, default: str = "") -> ttk.Entry:
            # Do NOT use textvariable=StringVar here — StringVar goes out of
            # scope and gets GC'd immediately, clearing the entry's value.
            e = ttk.Entry(parent, width=38)
            e.insert(0, default)
            e.grid(row=row, column=1, sticky='ew', padx=(0, 16), pady=(8, 0))
            return e

        grid = ttk.Frame(dialog, style='TFrame')
        grid.pack(fill='both', expand=True)
        grid.columnconfigure(1, weight=1)

        _lbl(grid, "Display Name:", 0)
        e_name = _ent(grid, 0, app.get("name", ""))

        _lbl(grid, "Executable Name:", 1)
        e_exe = _ent(grid, 1, app.get("exe_name", ""))

        _lbl(grid, "Executable Path:", 2)
        e_path = _ent(grid, 2, app.get("exe_path", ""))

        _lbl(grid, "Root Folder:", 3)
        e_root = _ent(grid, 3, app.get("root_folder", ""))

        _lbl(grid, "Daily Limit (min):", 4)
        daily_var = tk.IntVar(value=app.get("daily_limit_min", 0))
        ttk.Spinbox(grid, from_=0, to=1440, textvariable=daily_var, width=10).grid(
            row=4, column=1, sticky='w', padx=(0, 16), pady=(8, 0))

        _lbl(grid, "Weekly Limit (min):", 5)
        weekly_var = tk.IntVar(value=app.get("weekly_limit_min", 0))
        ttk.Spinbox(grid, from_=0, to=10080, textvariable=weekly_var, width=10).grid(
            row=5, column=1, sticky='w', padx=(0, 16), pady=(8, 0))

        def browse_exe() -> None:
            path = filedialog.askopenfilename(
                title="Select Executable",
                filetypes=[("Executable", "*.exe"), ("All", "*.*")],
                parent=dialog,
            )
            if path:
                e_path.delete(0, 'end')
                e_path.insert(0, os.path.normpath(path))
                e_root.delete(0, 'end')
                e_root.insert(0, os.path.dirname(os.path.normpath(path)))
                e_exe.delete(0, 'end')
                e_exe.insert(0, os.path.basename(path))

        ttk.Button(grid, text="Browse…", command=browse_exe).grid(
            row=2, column=2, padx=(4, 16), pady=(8, 0))

        # ── Category picker ───────────────────────────────────────────────────
        cat_sep = tk.Frame(dialog, bg='#0f3460', height=1)
        cat_sep.pack(fill='x', padx=16, pady=(14, 0))

        tk.Label(dialog, text="App Type", bg=BG, fg='#9090a0',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=16, pady=(8, 2))
        tk.Label(dialog,
                 text="Choose what kind of app this is — affects how Insights treats it.",
                 bg=BG, fg='#9090a0', font=('Segoe UI', 9)).pack(anchor='w', padx=16)

        _CATEGORIES = [
            # (label,          value,          group,        color)
            ("Gaming",         "Gaming",        "bad",        "#f87171"),
            ("Social",         "Social",        "bad",        "#f97316"),
            ("Entertainment",  "Entertainment", "bad",        "#fbbf24"),
            ("Social Media",   "Social Media",  "bad",        "#fb923c"),
            ("Development",    "Development",   "good",       "#4ade80"),
            ("Game Engine",    "Game Engine",   "good",       "#4ade80"),
            ("Work",           "Work",          "good",       "#4ade80"),
            ("Education",      "Education",     "good",       "#34d399"),
            ("Productivity",   "Productivity",  "good",       "#4ade80"),
            ("Design",         "Design",        "good",       "#4ade80"),
            ("Creative",       "Creative",      "good",       "#a3e635"),
            ("Custom",         "Custom",        "neutral",    "#9090a0"),
            ("Browser",        "Browser",       "neutral",    "#9090a0"),
            ("Other",          "Other",         "neutral",    "#9090a0"),
        ]

        current_cat = app.get("category", "Custom") or "Custom"
        _selected_cat = [current_cat]   # use list so inner funcs can mutate

        cat_outer = tk.Frame(dialog, bg=BG)
        cat_outer.pack(fill='x', padx=16, pady=(8, 0))

        # Section headers
        def _cat_section(parent, title, title_color):
            tk.Label(parent, text=title, bg=BG, fg=title_color,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(6, 2))
            row = tk.Frame(parent, bg=BG)
            row.pack(fill='x')
            return row

        bad_label  = _cat_section(cat_outer, "\u26d4  Distracting", "#f87171")
        good_label = _cat_section(cat_outer, "\u2705  Productive",   "#4ade80")
        neu_label  = _cat_section(cat_outer, "\u25cb  Neutral",      "#9090a0")

        _btn_refs = {}   # value -> button widget

        def _select(val):
            _selected_cat[0] = val
            for v, btn in _btn_refs.items():
                _, _, grp, col = next(c for c in _CATEGORIES if c[1] == v)
                is_sel = (v == val)
                btn.config(
                    bg=col if is_sel else '#0f3460',
                    fg='#0a1020' if is_sel else col,
                    relief='flat',
                    font=('Segoe UI', 9, 'bold') if is_sel else ('Segoe UI', 9),
                )

        for label, value, group, color in _CATEGORIES:
            parent_row = bad_label if group == "bad" else (good_label if group == "good" else neu_label)
            is_sel = (value == current_cat)
            btn = tk.Button(
                parent_row, text=label,
                bg=color if is_sel else '#0f3460',
                fg='#0a1020' if is_sel else color,
                activebackground=color, activeforeground='#0a1020',
                font=('Segoe UI', 9, 'bold') if is_sel else ('Segoe UI', 9),
                relief='flat', bd=0, padx=10, pady=4, cursor='hand2',
                command=lambda v=value: _select(v),
            )
            btn.pack(side='left', padx=(0, 4), pady=1)
            _btn_refs[value] = btn

        # ── Buttons ───────────────────────────────────────────────────────────
        tk.Frame(dialog, bg='#0f3460', height=1).pack(fill='x', padx=16, pady=(14, 0))

        btn_frame = ttk.Frame(dialog, style='TFrame')
        btn_frame.pack(fill='x', pady=(8, 12), padx=16)

        def save() -> None:
            new_exe  = e_exe.get().strip()
            new_path = e_path.get().strip()
            # The edit dialog is another route to pointing an entry at a
            # protected binary, so it needs the same guard as the add dialogs.
            if self._reject_if_protected(new_exe, new_path):
                return
            self.db.update_tracked_app(
                app_id,
                name=e_name.get().strip() or app["name"],
                exe_name=new_exe,
                exe_path=new_path,
                root_folder=e_root.get().strip(),
                category=_selected_cat[0],
            )
            self.db.set_app_limits(app_id, daily_var.get(), weekly_var.get())
            dialog.destroy()
            self.refresh()

        ttk.Button(btn_frame, text="Save", command=save, style='Accent.TButton').pack(side='right', padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right')


# ── Utility ───────────────────────────────────────────────────────────────────

def _ask_string(parent, title: str, prompt: str, default: str = ""):
    """Simple modal dialog that asks for a string value."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("360x140")
    dialog.configure(bg=BG)
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(False, False)

    tk.Label(dialog, text=prompt, bg=BG, fg=TEXT, font=('Segoe UI', 10),
             wraplength=340, justify='left').pack(padx=16, pady=(16, 6), anchor='w')

    var = tk.StringVar(value=default)
    entry = ttk.Entry(dialog, textvariable=var, width=38)
    entry.pack(padx=16, fill='x')
    entry.select_range(0, 'end')
    entry.focus_set()

    result = [None]

    def ok(event=None) -> None:
        result[0] = var.get().strip()
        dialog.destroy()

    def cancel() -> None:
        dialog.destroy()

    entry.bind('<Return>', ok)
    entry.bind('<Escape>', lambda e: cancel())

    btn_frame = ttk.Frame(dialog, style='TFrame')
    btn_frame.pack(fill='x', padx=16, pady=(10, 12))
    ttk.Button(btn_frame, text="OK", command=ok, style='Accent.TButton').pack(side='right', padx=(6, 0))
    ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side='right')

    dialog.wait_window()
    return result[0]
