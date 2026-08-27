"""
database.py - SQLite storage for FocusGuard.
"""

import os
import sqlite3
import threading
from datetime import timedelta, date

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FocusGuard")

# Schema version. Bump this and add a matching entry to _MIGRATIONS whenever the
# schema changes; the runner steps an existing database forward one version at a
# time on startup. Without it, adding a column silently breaks every install
# that already exists.
SCHEMA_VERSION = 1

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


# Indices. Without these every get_today_usage_sec() is a full table scan, and
# the kill watcher runs one per tracked app every five seconds against a table
# that grows without bound.
_CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_app_date "
    "ON usage_sessions (app_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_date "
    "ON usage_sessions (date);",
]

# version -> list of statements taking the schema from (version - 1) to version.
# Version 1 is the base schema, created directly, so it has no migration entry.
_MIGRATIONS: dict = {}


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
        # check_same_thread=False silences Python's safety check without
        # providing any safety, and this connection is written from the monitor
        # thread, the kill watcher and the Tk main thread. This lock is what
        # actually makes that safe.
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._create_tables()
        self._migrate()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(_CREATE_TRACKED_APPS)
            self._conn.execute(_CREATE_USAGE_SESSIONS)
            for statement in _CREATE_INDICES:
                self._conn.execute(statement)

    def _migrate(self) -> None:
        """
        Step an existing database forward to SCHEMA_VERSION.

        A brand-new database is stamped at the current version because
        _create_tables() has just built the latest schema. An existing one runs
        each migration in order, so an install from any earlier version ends up
        current instead of crashing on a missing column.
        """
        with self._lock:
            current = self._conn.execute("PRAGMA user_version;").fetchone()[0]

            if current == 0:
                # Either brand new, or created before versioning existed. Both
                # match the version 1 schema, so stamp rather than migrate.
                with self._lock, self._conn:
                    self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
                return

            if current > SCHEMA_VERSION:
                # Opened by a newer build. Leave it alone rather than corrupt it.
                raise RuntimeError(
                    f"Database schema version {current} is newer than this "
                    f"build supports ({SCHEMA_VERSION}). Please update FocusGuard."
                )

            for version in range(current + 1, SCHEMA_VERSION + 1):
                with self._lock, self._conn:
                    for statement in _MIGRATIONS.get(version, []):
                        self._conn.execute(statement)
                    self._conn.execute(f"PRAGMA user_version = {version};")

    @property
    def schema_version(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA user_version;").fetchone()[0]

    def _fetchall(self, sql: str, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                return []
            return [_row_to_dict(cur, r) for r in rows]

    def _fetchone(self, sql: str, params=()):
        with self._lock:
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
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO tracked_apps (name, exe_name, exe_path, root_folder, category)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, exe_name, exe_path, root_folder, category),
            )
        return cur.lastrowid

    def remove_tracked_app(self, app_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM tracked_apps WHERE id = ?;", (app_id,))

    def set_app_enabled(self, app_id: int, enabled: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE tracked_apps SET enabled = ? WHERE id = ?;",
                (1 if enabled else 0, app_id),
            )

    def set_app_limits(self, app_id: int, daily_min: int, weekly_min: int) -> None:
        with self._lock, self._conn:
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
        with self._lock, self._conn:
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
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO usage_sessions (app_id, date, start_time)
                   VALUES (?, ?, ?)""",
                (app_id, today, start_time_iso),
            )
        return cur.lastrowid

    def update_session_duration(self, session_id: int, duration_sec: int) -> None:
        """Save current duration mid-session so data isn't lost on crash."""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE usage_sessions SET duration_sec = ? WHERE id = ?;",
                (duration_sec, session_id),
            )

    def end_session(self, session_id: int, end_time_iso: str, duration_sec: int) -> None:
        with self._lock, self._conn:
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

    def delete_all_data(self, include_apps: bool = True) -> None:
        """
        Delete the user's recorded data.

        The UI reports this as "All usage data has been deleted", so it has to
        be true: sessions AND the tracked-app list, which is itself a record of
        what the user runs. Pass include_apps=False to clear history only.

        The diagnostic log lives outside the database and is removed by
        delete_log_file(); the caller is responsible for both.
        """
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM usage_sessions;")
            if include_apps:
                self._conn.execute("DELETE FROM tracked_apps;")
            # Reclaim the space rather than leaving deleted rows readable in
            # the file — this is a privacy feature, not just a reset.
            self._conn.execute("DELETE FROM sqlite_sequence "
                               "WHERE name IN ('usage_sessions', 'tracked_apps');")
        with self._lock:
            self._conn.execute("VACUUM;")

    def delete_log_file(self) -> bool:
        """
        Remove the diagnostic logs, which contain a plaintext record of every
        app the user opened.

        Covers rotated backups and the pre-1.0 monitor.log, not just the live
        file -- deleting only the current one would leave the history behind,
        which is exactly the BL-06 mistake in a different place.

        Returns True if at least one file was removed.
        """
        from core.logging_setup import log_paths

        candidates = log_paths(self._dir) + [os.path.join(self._dir, "monitor.log")]
        removed = False
        for path in candidates:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    removed = True
            except OSError:
                continue
        return removed

    def close(self) -> None:
        with self._lock:
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
