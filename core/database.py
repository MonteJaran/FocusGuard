"""
database.py - SQLite storage for FocusGuard.
"""

import os
import sqlite3
from datetime import timedelta, date

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FocusGuard")

_CREATE_TRACKED_APPS = """
CREATE TABLE IF NOT EXISTS tracked_apps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    exe_name        TEXT,
    exe_path        TEXT,
    root_folder     TEXT,
    category        TEXT    DEFAULT 'Custom',
    enabled         INTEGER DEFAULT 1,
    daily_limit_min INTEGER DEFAULT 0,
    weekly_limit_min INTEGER DEFAULT 0,
    added_at        TEXT    DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_USAGE_SESSIONS = """
CREATE TABLE IF NOT EXISTS usage_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id       INTEGER NOT NULL,
    date         TEXT    NOT NULL,
    start_time   TEXT    NOT NULL,
    end_time     TEXT,
    duration_sec INTEGER DEFAULT 0,
    FOREIGN KEY (app_id) REFERENCES tracked_apps(id) ON DELETE CASCADE
);
"""


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Convert a sqlite3 row tuple to a dictionary using column names."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row, strict=True))


class Database:
    def __init__(self, data_dir: str = "") -> None:
        # data_dir is injectable so tests can run against a temp directory
        # instead of the real %LOCALAPPDATA%.
        self._dir = data_dir or _DATA_DIR
        os.makedirs(self._dir, exist_ok=True)
        self._db_path = os.path.join(self._dir, "focusguard.db")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._create_tables()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        with self._conn:
            self._conn.execute(_CREATE_TRACKED_APPS)
            self._conn.execute(_CREATE_USAGE_SESSIONS)

    def _fetchall(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return []
        return [_row_to_dict(cur, r) for r in rows]

    def _fetchone(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_dict(cur, row)

    # ── Apps ─────────────────────────────────────────────────────────────────

    def get_all_tracked_apps(self):
        return self._fetchall("SELECT * FROM tracked_apps ORDER BY name;")

    def add_tracked_app(
        self,
        name: str,
        exe_name: str = "",
        exe_path: str = "",
        root_folder: str = "",
        category: str = "Custom",
    ) -> int:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO tracked_apps (name, exe_name, exe_path, root_folder, category)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, exe_name, exe_path, root_folder, category),
            )
        return cur.lastrowid

    def remove_tracked_app(self, app_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM tracked_apps WHERE id = ?;", (app_id,))

    def set_app_enabled(self, app_id: int, enabled: bool) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE tracked_apps SET enabled = ? WHERE id = ?;",
                (1 if enabled else 0, app_id),
            )

    def set_app_limits(self, app_id: int, daily_min: int, weekly_min: int) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE tracked_apps SET daily_limit_min = ?, weekly_limit_min = ? WHERE id = ?;",
                (daily_min, weekly_min, app_id),
            )

    def get_app_by_exe_name(self, exe_name: str):
        return self._fetchone(
            "SELECT * FROM tracked_apps WHERE LOWER(exe_name) = LOWER(?) LIMIT 1;",
            (exe_name,),
        )

    def update_tracked_app(self, app_id: int, name: str, exe_name: str,
                           exe_path: str, root_folder: str, category: str = "") -> None:
        with self._conn:
            if category:
                self._conn.execute(
                    """UPDATE tracked_apps
                       SET name = ?, exe_name = ?, exe_path = ?, root_folder = ?, category = ?
                       WHERE id = ?;""",
                    (name, exe_name, exe_path, root_folder, category, app_id),
                )
            else:
                self._conn.execute(
                    """UPDATE tracked_apps
                       SET name = ?, exe_name = ?, exe_path = ?, root_folder = ?
                       WHERE id = ?;""",
                    (name, exe_name, exe_path, root_folder, app_id),
                )

    # ── Sessions ─────────────────────────────────────────────────────────────

    def start_session(self, app_id: int, start_time_iso: str) -> int:
        today = start_time_iso[:10]  # YYYY-MM-DD
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO usage_sessions (app_id, date, start_time)
                   VALUES (?, ?, ?)""",
                (app_id, today, start_time_iso),
            )
        return cur.lastrowid

    def update_session_duration(self, session_id: int, duration_sec: int) -> None:
        """Save current duration mid-session so data isn't lost on crash."""
        with self._conn:
            self._conn.execute(
                "UPDATE usage_sessions SET duration_sec = ? WHERE id = ?;",
                (duration_sec, session_id),
            )

    def end_session(self, session_id: int, end_time_iso: str, duration_sec: int) -> None:
        with self._conn:
            self._conn.execute(
                """UPDATE usage_sessions
                   SET end_time = ?, duration_sec = ?
                   WHERE id = ?;""",
                (end_time_iso, duration_sec, session_id),
            )

    def get_today_usage_sec(self, app_id: int) -> int:
        today = date.today().isoformat()
        row = self._fetchone(
            """SELECT COALESCE(SUM(duration_sec), 0) AS total
               FROM usage_sessions
               WHERE app_id = ? AND date = ?;""",
            (app_id, today),
        )
        return int(row["total"]) if row else 0

    def get_week_usage_sec(self, app_id: int) -> int:
        week_ago = (date.today() - timedelta(days=6)).isoformat()
        today = date.today().isoformat()
        row = self._fetchone(
            """SELECT COALESCE(SUM(duration_sec), 0) AS total
               FROM usage_sessions
               WHERE app_id = ? AND date BETWEEN ? AND ?;""",
            (app_id, week_ago, today),
        )
        return int(row["total"]) if row else 0

    def get_usage_history(self, app_id: int, days: int = 30):
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        return self._fetchall(
            """SELECT date, COALESCE(SUM(duration_sec), 0) AS total_sec
               FROM usage_sessions
               WHERE app_id = ? AND date >= ?
               GROUP BY date
               ORDER BY date;""",
            (app_id, cutoff),
        )

    def get_all_usage_today(self):
        today = date.today().isoformat()
        return self._fetchall(
            """SELECT s.app_id, a.name, COALESCE(SUM(s.duration_sec), 0) AS duration_sec
               FROM usage_sessions s
               JOIN tracked_apps a ON a.id = s.app_id
               WHERE s.date = ?
               GROUP BY s.app_id, a.name
               ORDER BY duration_sec DESC;""",
            (today,),
        )

    def get_all_apps_week_usage(self):
        """All tracked apps with their total usage this week, sorted by most used."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()
        today    = date.today().isoformat()
        return self._fetchall(
            """SELECT s.app_id, a.name, a.category,
                      COALESCE(SUM(s.duration_sec), 0) AS total_sec
               FROM usage_sessions s
               JOIN tracked_apps a ON a.id = s.app_id
               WHERE s.date BETWEEN ? AND ?
               GROUP BY s.app_id, a.name, a.category
               ORDER BY total_sec DESC;""",
            (week_ago, today),
        )

    def get_peak_hours(self, days=7):
        """Usage grouped by hour-of-day for the last N days."""
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        return self._fetchall(
            """SELECT CAST(strftime('%H', start_time) AS INTEGER) AS hour,
                      COALESCE(SUM(duration_sec), 0) AS total_sec
               FROM usage_sessions
               WHERE date >= ?
               GROUP BY hour
               ORDER BY hour;""",
            (cutoff,),
        )

    def get_category_usage_week(self):
        """Usage grouped by app category for this week."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()
        today    = date.today().isoformat()
        return self._fetchall(
            """SELECT a.category,
                      COALESCE(SUM(s.duration_sec), 0) AS total_sec
               FROM usage_sessions s
               JOIN tracked_apps a ON a.id = s.app_id
               WHERE s.date BETWEEN ? AND ?
               GROUP BY a.category
               ORDER BY total_sec DESC;""",
            (week_ago, today),
        )

    def delete_all_data(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM usage_sessions;")

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def data_dir(self) -> str:
        return self._dir
