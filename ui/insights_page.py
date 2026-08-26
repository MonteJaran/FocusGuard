"""
insights_page.py - Eye-opening usage insights for FocusGuard.
Refreshed only when the tab is selected, so scroll position is never lost.
"""

import tkinter as tk
from tkinter import ttk

BG      = '#1a1a2e'
BG2     = '#16213e'
BG3     = '#0f3460'
ACCENT  = '#e94560'
TEXT    = '#e0e0e0'
TEXT2   = '#9090a0'
SUCCESS = '#4ade80'
WARNING = '#fbbf24'
ERROR   = '#f87171'
GOLD    = '#f59e0b'
PURPLE  = '#8b5cf6'
CYAN    = '#06b6d4'

# ── Category classification ────────────────────────────────────────────────────
# Productive = good, celebrated
# Distracting = flagged as time cost
# Neutral = shown without judgement

_PRODUCTIVE   = {'Development', 'Game Engine', 'Productivity', 'Work',
                 'Education', 'Design', 'Creative'}
_DISTRACTING  = {'Gaming', 'Social', 'Entertainment', 'Social Media', 'Browser'}
# Everything else → neutral

# ── World-average reference data (approximate, sourced from public studies) ────
# All values in hours per week
_WORLD_AVG = {
    'Gaming':      7.0,   # Newzoo / Limelight Networks global avg ~7 h/wk
    'Social':      17.5,  # DataReportal 2024: ~2.5 h/day globally
    'Entertainment': 14.0,
    'Social Media': 17.5,
    'Development': 28.0,  # ~4 h/day focused coding (dev survey averages)
    'Work':        35.0,
    'Productivity': 20.0,
    'Education':   5.0,
}

# ── Time helpers ──────────────────────────────────────────────────────────────

def _fmt(sec):
    if sec <= 0:
        return "0m"
    h = sec // 3600
    m = (sec % 3600) // 60
    return ("%dh %dm" % (h, m)) if h and m else ("%dh" % h if h else "%dm" % m)

def _hrs(sec):
    return sec / 3600.0

# Equivalent durations in seconds
_MOVIE_SEC   = 110 * 60
_BOOK_SEC    = 360 * 60
_WORKDAY_SEC = 480 * 60


class InsightsPage(ttk.Frame):

    def __init__(self, parent, db, config, monitor):
        super().__init__(parent, style='TFrame')
        self.db      = db
        self.config  = config
        self.monitor = monitor
        self._built  = False
        self._build_shell()

    # ── Scrollable shell (built once) ─────────────────────────────────────────

    def _build_shell(self):
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient='vertical', command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._canvas.pack(side='left', fill='both', expand=True)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor='nw')

        self._inner.bind('<Configure>',
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox('all')))
        self._canvas.bind('<Configure>',
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        self._canvas.bind_all('<MouseWheel>',
            lambda e: self._canvas.yview_scroll(-(e.delta // 120), 'units'))

    # ── Public refresh (called on tab-select only) ────────────────────────────

    def refresh(self):
        # Save scroll position
        try:
            y_frac = self._canvas.yview()[0]
        except Exception:
            y_frac = 0.0

        # Rebuild content
        for w in self._inner.winfo_children():
            w.destroy()

        try:
            week_apps  = self.db.get_all_apps_week_usage()
        except Exception:
            week_apps  = []
        try:
            peak_hours = self.db.get_peak_hours(7)
        except Exception:
            peak_hours = []
        try:
            categories = self.db.get_category_usage_week()
        except Exception:
            categories = []

        self._draw_header()
        self._draw_top_apps(week_apps)
        self._draw_distracting(week_apps, categories)
        self._draw_productive(week_apps, categories)
        self._draw_peak_hours(peak_hours)
        self._draw_categories(categories)
        self._draw_premium(week_apps)

        # Restore scroll after layout settles
        self._canvas.after(30, lambda: self._canvas.yview_moveto(y_frac))

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _draw_header(self):
        hdr = tk.Frame(self._inner, bg=BG)
        hdr.pack(fill='x', padx=16, pady=(14, 2))
        tk.Label(hdr, text="Insights", bg=BG, fg=TEXT,
                 font=('Segoe UI', 16, 'bold')).pack(side='left')
        tk.Label(hdr, text="  How your habits compare to the world",
                 bg=BG, fg=TEXT2, font=('Segoe UI', 10)).pack(side='left', pady=4)
        ttk.Separator(self._inner).pack(fill='x', padx=16, pady=(4, 8))

    def _section(self, title, color=ACCENT):
        tk.Label(self._inner, text=title, bg=BG, fg=color,
                 font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=16, pady=(10, 2))
        f = tk.Frame(self._inner, bg=BG)
        f.pack(fill='x', padx=10, pady=(0, 4))
        return f

    def _card(self, parent, col=0, row=0, colspan=1):
        c = tk.Frame(parent, bg=BG2, padx=14, pady=12)
        c.grid(row=row, column=col, columnspan=colspan,
               sticky='nsew', padx=5, pady=5)
        return c

    def _no_data(self, frame, msg="No usage data yet — open some tracked apps first."):
        tk.Label(frame, text=msg, bg=BG, fg=TEXT2,
                 font=('Segoe UI', 10), padx=6).pack(anchor='w')

    # ── Top 3 this week ───────────────────────────────────────────────────────

    def _draw_top_apps(self, apps):
        f = self._section("This Week's Top Apps")
        if not apps:
            self._no_data(f)
            return
        medals  = ["#1", "#2", "#3"]
        m_color = [GOLD, TEXT2, '#cd7f32']
        for i in range(min(3, len(apps))):
            f.columnconfigure(i, weight=1)
        for i, app in enumerate(apps[:3]):
            sec  = app.get("total_sec", 0)
            cat  = app.get("category", "Custom")
            is_bad  = cat in _DISTRACTING
            is_good = cat in _PRODUCTIVE
            time_color = ERROR if is_bad else (SUCCESS if is_good else ACCENT)

            card = self._card(f, col=i, row=0)
            tk.Label(card, text=medals[i], bg=BG2, fg=m_color[i],
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w')
            tk.Label(card, text=app["name"], bg=BG2, fg=TEXT,
                     font=('Segoe UI', 12, 'bold'),
                     wraplength=160, justify='left').pack(anchor='w')
            tk.Label(card, text=cat, bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w')
            tk.Label(card, text=_fmt(sec), bg=BG2, fg=time_color,
                     font=('Segoe UI', 22, 'bold')).pack(anchor='w', pady=(6, 0))
            tk.Label(card, text="this week", bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w')

    # ── Distracting apps — "time cost" framing ────────────────────────────────

    def _draw_distracting(self, apps, categories):
        bad_apps = [a for a in apps if a.get("category", "") in _DISTRACTING]
        if not bad_apps:
            return

        f = self._section("Time You Could Reclaim", color=ERROR)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        top = bad_apps[0]
        week_sec  = top.get("total_sec", 0)
        week_hrs  = _hrs(week_sec)
        year_days = week_hrs * 52 / 24
        month_sec = week_sec * 4

        # Card A — year projection
        card_a = self._card(f, col=0, row=0)
        tk.Label(card_a, text="This year you will waste",
                 bg=BG2, fg=TEXT2, font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(card_a, text="%.0f days" % year_days,
                 bg=BG2, fg=ERROR, font=('Segoe UI', 30, 'bold')).pack(anchor='w')
        tk.Label(card_a, text="on %s" % top["name"],
                 bg=BG2, fg=TEXT, font=('Segoe UI', 11, 'bold')).pack(anchor='w')

        # World avg comparison for this category
        cat       = top.get("category", "")
        world_avg = _WORLD_AVG.get(cat, 7.0)   # hrs/week
        diff      = week_hrs - world_avg
        if diff > 0:
            cmp_text = "+%.1f h/wk above world average (%.0f h/wk)" % (diff, world_avg)
            cmp_color = ERROR
        else:
            cmp_text = "%.1f h/wk below world average (%.0f h/wk)" % (abs(diff), world_avg)
            cmp_color = SUCCESS
        tk.Label(card_a, text=cmp_text, bg=BG2, fg=cmp_color,
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(6, 0))

        # Card B — equivalents
        card_b = self._card(f, col=1, row=0)
        tk.Label(card_b, text="That monthly time equals...",
                 bg=BG2, fg=TEXT2, font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 8))
        equivs = [
            ("\U0001f3ac", "%.0f movies" % (month_sec / _MOVIE_SEC), "you could have watched"),
            ("\U0001f4da", "%.0f books"  % (month_sec / _BOOK_SEC),  "you could have read"),
            ("\U0001f4bc", "%.0f workdays" % (month_sec / _WORKDAY_SEC), "of lost productivity"),
        ]
        for icon, val, sub in equivs:
            row = tk.Frame(card_b, bg=BG2)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=icon, bg=BG2, font=('Segoe UI', 11)).pack(side='left')
            tk.Label(row, text=" %s " % val, bg=BG2, fg=WARNING,
                     font=('Segoe UI', 10, 'bold')).pack(side='left')
            tk.Label(row, text=sub, bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(side='left')

        # Additional bad apps (smaller cards)
        if len(bad_apps) > 1:
            for j, app in enumerate(bad_apps[1:4]):
                col_idx = j % 2
                row_idx = 1 + j // 2
                f.columnconfigure(col_idx, weight=1)
                sec      = app.get("total_sec", 0)
                hrs      = _hrs(sec)
                cat2     = app.get("category", "")
                world2   = _WORLD_AVG.get(cat2, 7.0)
                diff2    = hrs - world2
                c = self._card(f, col=col_idx, row=row_idx)
                tk.Label(c, text=app["name"], bg=BG2, fg=TEXT,
                         font=('Segoe UI', 10, 'bold')).pack(anchor='w')
                tk.Label(c, text=_fmt(sec) + " this week", bg=BG2, fg=ERROR,
                         font=('Segoe UI', 9)).pack(anchor='w')
                sign = "+" if diff2 > 0 else ""
                ccolor = ERROR if diff2 > 0 else SUCCESS
                tk.Label(c, text="%s%.1f h vs world avg" % (sign, diff2),
                         bg=BG2, fg=ccolor, font=('Segoe UI', 8)).pack(anchor='w')

    # ── Productive apps — positive reinforcement ──────────────────────────────

    def _draw_productive(self, apps, categories):
        good_apps = [a for a in apps if a.get("category", "") in _PRODUCTIVE]
        if not good_apps:
            return

        f = self._section("Great Habits  \u2714", color=SUCCESS)
        for i in range(min(3, len(good_apps))):
            f.columnconfigure(i, weight=1)

        for i, app in enumerate(good_apps[:3]):
            sec      = app.get("total_sec", 0)
            hrs      = _hrs(sec)
            cat      = app.get("category", "")
            world    = _WORLD_AVG.get(cat, 20.0)
            diff     = hrs - world

            # Percentile estimate (rough, based on normal distribution assumption)
            if diff > world * 0.5:
                pct_msg = "Top 10% globally"
                pct_col = GOLD
            elif diff > 0:
                pct_msg = "Top 25% globally"
                pct_col = SUCCESS
            elif diff > -world * 0.3:
                pct_msg = "Around world average"
                pct_col = WARNING
            else:
                pct_msg = "Below world average"
                pct_col = TEXT2

            card = self._card(f, col=i, row=0)
            tk.Label(card, text="\u2705 " + app["name"], bg=BG2, fg=SUCCESS,
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w')
            tk.Label(card, text=cat, bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w')
            tk.Label(card, text=_fmt(sec), bg=BG2, fg=SUCCESS,
                     font=('Segoe UI', 22, 'bold')).pack(anchor='w', pady=(6, 0))
            tk.Label(card, text="this week", bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w')
            tk.Label(card, text=pct_msg, bg=BG2, fg=pct_col,
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(6, 0))
            world_str = "World avg: %.0f h/wk" % world
            tk.Label(card, text=world_str, bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w')

    # ── Peak hours bar chart ──────────────────────────────────────────────────

    def _draw_peak_hours(self, hours_data):
        f = self._section("Your Peak Hours  (last 7 days)")
        card = tk.Frame(f, bg=BG2, padx=14, pady=12)
        card.pack(fill='x', padx=5, pady=5)

        if not hours_data:
            tk.Label(card, text="Not enough data yet — keep tracking for a few days.",
                     bg=BG2, fg=TEXT2, font=('Segoe UI', 10)).pack(anchor='w')
            return

        hour_map = {int(r["hour"]): int(r["total_sec"]) for r in hours_data}
        max_sec  = max(hour_map.values()) if hour_map else 1
        peak_hr  = max(hour_map, key=hour_map.get)

        # Peak hour label
        def _12h(h):
            ap = "AM" if h < 12 else "PM"
            return "%d%s" % (h % 12 or 12, ap)

        tk.Label(card, text="Peak hour: %s \u2013 %s" % (_12h(peak_hr), _12h((peak_hr+1) % 24)),
                 bg=BG2, fg=WARNING, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 8))

        chart = tk.Frame(card, bg=BG2)
        chart.pack(fill='x')

        BAR_MAX = 60
        for hr in range(24):
            sec  = hour_map.get(hr, 0)
            bh   = max(2, int((sec / max_sec) * BAR_MAX)) if max_sec else 2
            col  = ACCENT if hr == peak_hr else (BG3 if sec > 0 else '#0a1525')
            cf   = tk.Frame(chart, bg=BG2)
            cf.pack(side='left', expand=True)
            tk.Frame(cf, bg=BG2, height=BAR_MAX - bh, width=16).pack()
            tk.Frame(cf, bg=col,  height=bh,           width=16).pack()
            lbl = ("%d" % (hr % 12 or 12)) if hr % 3 == 0 else ""
            tk.Label(cf, text=lbl, bg=BG2, fg=TEXT2, font=('Segoe UI', 6)).pack()

        tk.Label(card, text="12 AM on left  \u2192  11 PM on right",
                 bg=BG2, fg=TEXT2, font=('Segoe UI', 7)).pack(anchor='w', pady=(4, 0))

    # ── Category split ────────────────────────────────────────────────────────

    def _draw_categories(self, cats):
        f = self._section("Time by Category  (this week)")
        card = tk.Frame(f, bg=BG2, padx=14, pady=12)
        card.pack(fill='x', padx=5, pady=5)

        if not cats:
            tk.Label(card, text="No category data yet.",
                     bg=BG2, fg=TEXT2, font=('Segoe UI', 10)).pack(anchor='w')
            return

        total_sec = sum(c["total_sec"] for c in cats) or 1
        CAT_COLORS = {
            'Gaming':      ERROR,
            'Social':      '#f97316',
            'Entertainment': WARNING,
            'Social Media': '#f97316',
            'Development': SUCCESS,
            'Game Engine': PURPLE,
            'Productivity':SUCCESS,
            'Work':        SUCCESS,
            'Education':   CYAN,
            'Custom':      TEXT2,
        }
        LABELS = {
            'Gaming':      'Gaming  (distraction)',
            'Social':      'Social  (distraction)',
            'Entertainment':'Entertainment  (distraction)',
            'Development': 'Development  \u2714',
            'Game Engine': 'Game Engine  \u2714',
            'Productivity':'Productivity  \u2714',
            'Work':        'Work  \u2714',
            'Education':   'Education  \u2714',
        }

        for cat in cats:
            sec   = cat["total_sec"]
            pct   = sec / total_sec
            name  = cat["category"]
            color = CAT_COLORS.get(name, TEXT2)
            label = LABELS.get(name, name)

            row = tk.Frame(card, bg=BG2)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label, bg=BG2, fg=color,
                     font=('Segoe UI', 10), width=26, anchor='w').pack(side='left')
            bar_bg = tk.Frame(row, bg='#0a1525', height=18)
            bar_bg.pack(side='left', fill='x', expand=True, padx=(4, 8))
            bar_bg.update_idletasks()
            tk.Frame(bar_bg, bg=color, height=18).place(
                x=0, y=0, relwidth=max(pct, 0.01), height=18)
            tk.Label(row, text="%s  %.0f%%" % (_fmt(sec), pct * 100),
                     bg=BG2, fg=TEXT2, font=('Segoe UI', 9),
                     width=13, anchor='e').pack(side='right')

    # ── Premium teasers ───────────────────────────────────────────────────────

    def _draw_premium(self, apps):
        """
        Preview of insights that are planned but not built yet.

        These describe what each insight WILL do. They must never show an
        invented statistic about the user: a made-up "71% of the time" or
        "your score: 47/100", especially under a heading like "detected",
        reads as a real finding and is a false claim about that person's own
        data. See ROADMAP.md and AUDIT.md BL-02.
        """
        f = self._section("\u25cb  Advanced Insights  \u2014  Planned", color=TEXT2)

        teasers = [
            {
                "title":   "Distraction triggers",
                "preview": "Which app you tend to open\nright after closing another",
                "sub":     "Computed from your own session history",
            },
            {
                "title":   "Week-over-week trends",
                "preview": "How this week compares\nwith the weeks before it",
                "sub":     "Needs a few weeks of history to be meaningful",
            },
            {
                "title":   "Day-of-week breakdown",
                "preview": "Which days run longest,\nand by how much",
                "sub":     "Plan your week around your weak spots",
            },
        ]

        for i in range(3):
            f.columnconfigure(i, weight=1)

        for i, t in enumerate(teasers):
            card = self._card(f, col=i, row=0)
            tk.Label(card, text="\u25cb  " + t["title"],
                     bg=BG2, fg=TEXT, font=('Segoe UI', 9, 'bold')).pack(anchor='w')
            box = tk.Frame(card, bg=BG3, padx=10, pady=8)
            box.pack(fill='x', pady=(8, 4))
            tk.Label(box, text=t["preview"], bg=BG3, fg=TEXT2,
                     font=('Segoe UI', 9),
                     wraplength=170, justify='left').pack(anchor='w')
            tk.Label(card, text="Not available yet",
                     bg=BG2, fg=TEXT2, font=('Segoe UI', 8, 'bold')).pack(anchor='w')
            tk.Label(card, text=t["sub"], bg=BG2, fg=TEXT2,
                     font=('Segoe UI', 8)).pack(anchor='w', pady=(2, 0))
