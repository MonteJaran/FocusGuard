"""
monitor.py - Background monitoring thread for FocusGuard.
"""

import threading
import os
import traceback
from datetime import datetime

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

# Log file for diagnostics
_LOG_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "FocusGuard", "monitor.log"
)

# Optional notification support
def _send_notification(title: str, message: str, sound: bool = False) -> None:
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="FocusGuard",
            timeout=8,
        )
    except Exception:
        pass  # Graceful fallback: no notification

def _play_kill_sound() -> None:
    """Play the Windows exclamation sound asynchronously (thread-safe)."""
    try:
        import winsound
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        try:
            import winsound
            winsound.Beep(880, 200)
            winsound.Beep(660, 300)
        except Exception:
            pass


class Monitor:
    """
    Monitors running processes at a configurable poll interval.
    Updates session data in the database and fires callbacks on state changes.
    Thread-safe: DB writes happen on the monitor thread; callbacks are called
    from the monitor thread (UI must use root.after() if they touch widgets).
    """

    def __init__(self, db, config) -> None:
        self.db = db
        self.config = config
        self._thread = None  # type: threading.Thread
        self._stop_event = threading.Event()

        # app_id -> {'session_id': int, 'start_time': datetime}
        self.active_sessions = {}
        # set of app_ids currently detected as running
        self.running_apps = set()
        # list of callables: fn(event_type: str, data: dict)
        self.callbacks = []

        # Cache to avoid notifying the same limit breach repeatedly
        self._notified_limits = set()  # app_ids already warned today
        # Event to wake the monitor thread immediately for a poll
        self._poll_now = threading.Event()

        # Diagnostics visible to the UI
        self.last_poll_time = None          # datetime of last poll
        self.last_poll_proc_count = 0       # how many processes psutil saw
        self.last_poll_error = ""           # last error message if any
        self.psutil_available = _PSUTIL_AVAILABLE

        # Fast kill-watcher thread (runs every 5 s, only when auto_kill is on)
        self._kill_thread = None  # type: threading.Thread

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="FocusGuard-Monitor")
        self._thread.start()
        # Start fast kill-watcher (always running; only acts when setting is on)
        self._kill_thread = threading.Thread(target=self._kill_watcher, daemon=True,
                                             name="FocusGuard-KillWatcher")
        self._kill_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        # End all active sessions cleanly
        now = datetime.now()
        for _app_id, session in list(self.active_sessions.items()):
            try:
                duration = int((now - session["start_time"]).total_seconds())
                self.db.end_session(session["session_id"], now.isoformat(), duration)
            except Exception:
                pass
        self.active_sessions.clear()
        self.running_apps.clear()
        if self._thread:
            self._thread.join(timeout=5)

    def add_callback(self, fn) -> None:
        """Register a callback fn(event_type, data) for state changes."""
        if fn not in self.callbacks:
            self.callbacks.append(fn)

    def remove_callback(self, fn) -> None:
        if fn in self.callbacks:
            self.callbacks.remove(fn)

    def get_status(self) -> dict:
        """
        Return a snapshot of current status.
        Returns {app_id: {'running': bool, 'today_sec': int, 'week_sec': int}}
        """
        result = {}
        try:
            apps = self.db.get_all_tracked_apps()
            for app in apps:
                app_id = app["id"]
                result[app_id] = {
                    "running": app_id in self.running_apps,
                    "today_sec": self.db.get_today_usage_sec(app_id),
                    "week_sec": self.db.get_week_usage_sec(app_id),
                }
        except Exception:
            pass
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def trigger_poll(self) -> None:
        """Wake up the monitor thread to do an immediate poll."""
        self._poll_now.set()

    def _log(self, msg: str) -> None:
        """Write a timestamped line to the log file."""
        try:
            os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def _run(self) -> None:
        """Main monitor loop."""
        self._log(f"Monitor thread started. psutil_available={_PSUTIL_AVAILABLE}")
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                err = traceback.format_exc()
                self.last_poll_error = str(e)
                self._log(f"POLL ERROR: {err}")
            # Sleep until poll_interval elapses OR trigger_poll() is called
            self._poll_now.wait(timeout=self.config.get("poll_interval", 60))
            self._poll_now.clear()
        self._log("Monitor thread stopped.")

    def _kill_watcher(self) -> None:
        """
        Lightweight loop that runs every 5 seconds.
        When auto_kill_over_limit is ON it scans all running processes and
        immediately terminates any that are over their daily limit —
        regardless of the main poll interval.
        """
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=5)
            if self._stop_event.is_set():
                break
            if not self.config.get("auto_kill_over_limit", False):
                continue
            if not _PSUTIL_AVAILABLE:
                continue
            try:
                apps = self.db.get_all_tracked_apps()
                # Build current process name set once
                running_names = set()
                running_paths = set()
                for proc in psutil.process_iter(["name", "exe"]):
                    try:
                        n = (proc.info.get("name") or "").lower()
                        p = (proc.info.get("exe")  or "").lower().replace("\\", "/")
                        if n:
                            running_names.add(n)
                        if p:
                            running_paths.add(p)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                for app in apps:
                    if not app.get("enabled", 1):
                        continue
                    daily_limit = app.get("daily_limit_min", 0) or 0
                    if daily_limit <= 0:
                        continue

                    exe_name = (app.get("exe_name") or "").lower().strip()
                    exe_path = (app.get("exe_path") or "").lower().replace("\\", "/").strip()

                    # Is this app currently running at all?
                    is_running = (exe_name and exe_name in running_names) or \
                                 (exe_path and exe_path in running_paths)
                    if not is_running:
                        continue

                    # Is it over the limit (include current active session)?
                    app_id = app["id"]
                    today_sec = self.db.get_today_usage_sec(app_id)
                    if app_id in self.active_sessions:
                        elapsed = (datetime.now() - self.active_sessions[app_id]["start_time"]).total_seconds()
                        today_sec += int(elapsed)

                    if today_sec >= daily_limit * 60:
                        self._log(f"KillWatcher: '{app['name']}' over limit — killing.")
                        killed = self._kill_app(app["name"], exe_name, exe_path)
                        if killed:
                            if self.config.get("notifications_enabled", True):
                                _send_notification(
                                    "FocusGuard — App Closed",
                                    f"{app['name']} was closed: daily limit of "
                                    f"{daily_limit} min reached.",
                                    sound=False,
                                )
                            if self.config.get("notification_sound", False):
                                _play_kill_sound()
                            self._fire("app_killed", {"app_id": app_id,
                                                      "name": app["name"],
                                                      "limit_min": daily_limit})
            except Exception as e:
                self._log(f"KillWatcher error: {e}")

    def _poll(self) -> None:
        """Check running processes, update sessions, check limits."""
        running_names, running_paths = self._get_running_info()
        self.last_poll_time = datetime.now()
        self.last_poll_proc_count = len(running_names)
        self._log(f"Poll: {len(running_names)} processes found. "
                  f"Tracking {len(self.db.get_all_tracked_apps())} apps.")

        apps = self.db.get_all_tracked_apps()
        enabled_apps = [a for a in apps if a.get("enabled", 1)]

        now = datetime.now()
        changed = False

        for app in enabled_apps:
            app_id = app["id"]
            exe_name = (app.get("exe_name") or "").lower().strip()
            exe_path = (app.get("exe_path") or "").lower().replace("\\", "/").strip()

            if not exe_name and not exe_path:
                self._log(f"  SKIP '{app['name']}': no exe_name or exe_path stored")
                continue

            # Match by exe name OR by full executable path (more robust)
            match_name = exe_name and exe_name in running_names
            match_path = exe_path and exe_path in running_paths
            is_running = match_name or match_path

            self._log(f"  '{app['name']}': exe_name='{exe_name}' match={match_name} | "
                      f"exe_path='{exe_path[:40]}' match={match_path} => running={is_running}")

            if is_running and app_id not in self.active_sessions:
                # App just started — check if it's already over the daily limit
                if self.config.get("auto_kill_over_limit", False) and \
                        self._is_over_daily_limit(app_id, app):
                    self._log(f"'{app['name']}' launched but already over limit — killing.")
                    killed = self._kill_app(app["name"], exe_name, exe_path)
                    if killed:
                        if self.config.get("notifications_enabled", True):
                            _send_notification(
                                "FocusGuard — App Blocked",
                                f"{app['name']} was blocked: you have already reached "
                                f"your daily limit of {app.get('daily_limit_min', 0)} min.",
                                sound=False,
                            )
                        if self.config.get("notification_sound", False):
                            _play_kill_sound()
                        self._fire("app_killed", {"app_id": app_id, "name": app["name"],
                                                  "limit_min": app.get("daily_limit_min", 0)})
                        continue  # don't start a session for it

                try:
                    session_id = self.db.start_session(app_id, now.isoformat())
                    self.active_sessions[app_id] = {
                        "session_id": session_id,
                        "start_time": now,
                    }
                    self.running_apps.add(app_id)
                    changed = True
                    self._fire("app_started", {"app_id": app_id, "name": app["name"]})
                except Exception:
                    pass

            elif not is_running and app_id in self.active_sessions:
                # App just stopped
                session = self.active_sessions.pop(app_id)
                self.running_apps.discard(app_id)
                changed = True
                try:
                    duration = int((now - session["start_time"]).total_seconds())
                    self.db.end_session(session["session_id"], now.isoformat(), duration)
                    self._fire("app_stopped", {"app_id": app_id, "name": app["name"]})
                    # Clear limit notification cache on stop so it can warn again next run
                    self._notified_limits.discard(app_id)
                except Exception:
                    pass

            elif is_running and app_id in self.active_sessions:
                # App still running — check limits
                daily_limit = app.get("daily_limit_min", 0)
                if daily_limit and daily_limit > 0:
                    self._check_limits(app_id, app["name"], exe_name, exe_path, daily_limit)

        # Save progress for all still-running sessions so data survives crashes
        now_save = datetime.now()
        for _app_id, session in list(self.active_sessions.items()):
            try:
                duration = int((now_save - session["start_time"]).total_seconds())
                self.db.update_session_duration(session["session_id"], duration)
            except Exception:
                pass

        if changed:
            self._fire("status_update", {})

    def _get_running_info(self):
        """Return (exe_names, exe_paths) — two sets of lowercased strings."""
        if not _PSUTIL_AVAILABLE:
            self._log("psutil NOT available — cannot detect processes!")
            return set(), set()
        names = set()
        paths = set()
        try:
            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    n = (proc.info.get("name") or "").lower()
                    p = (proc.info.get("exe") or "").lower().replace("\\", "/")
                    if n:
                        names.add(n)
                    if p:
                        paths.add(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            self._log(f"psutil iteration error: {e}")
        return names, paths

    def _kill_app(self, app_name: str, exe_name: str, exe_path: str) -> bool:
        """
        Force-terminate all processes matching exe_name or exe_path.
        Returns True if at least one process was killed.
        """
        if not _PSUTIL_AVAILABLE:
            return False
        killed = False
        exe_name_l = exe_name.lower().strip()
        exe_path_l  = exe_path.lower().replace("\\", "/").strip()
        try:
            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    pexe  = (proc.info.get("exe")  or "").lower().replace("\\", "/")
                    if (exe_name_l and pname == exe_name_l) or \
                       (exe_path_l  and pexe  == exe_path_l):
                        proc.kill()
                        killed = True
                        self._log(f"Killed process '{pname}' (limit exceeded for {app_name})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            self._log(f"Error killing {app_name}: {e}")
        return killed

    def _is_over_daily_limit(self, app_id: int, app: dict) -> bool:
        """Return True if the app has already used up its daily limit."""
        daily_limit_min = app.get("daily_limit_min", 0) or 0
        if daily_limit_min <= 0:
            return False
        try:
            today_sec = self.db.get_today_usage_sec(app_id)
            return today_sec >= daily_limit_min * 60
        except Exception:
            return False

    def _check_limits(self, app_id: int, app_name: str, exe_name: str,
                      exe_path: str, daily_limit_min: int) -> None:
        """Notify and optionally kill app if it has exceeded or is near its daily limit."""
        try:
            today_sec = self.db.get_today_usage_sec(app_id)
            # Add current session time for accuracy
            if app_id in self.active_sessions:
                elapsed = (datetime.now() - self.active_sessions[app_id]["start_time"]).total_seconds()
                today_sec += int(elapsed)

            limit_sec = daily_limit_min * 60
            warn_pct  = self.config.get("warn_at_percent", 80)
            usage_pct = (today_sec / limit_sec * 100) if limit_sec > 0 else 0

            notify_key = f"{app_id}_{int(usage_pct // 10) * 10}"

            if usage_pct >= 100:
                # Auto-kill if enabled
                if self.config.get("auto_kill_over_limit", False):
                    killed = self._kill_app(app_name, exe_name, exe_path)
                    if killed:
                        if self.config.get("notifications_enabled", True):
                            _send_notification(
                                "FocusGuard — App Closed",
                                f"{app_name} was closed automatically: daily limit of "
                                f"{daily_limit_min} min reached.",
                                sound=False,
                            )
                        if self.config.get("notification_sound", False):
                            _play_kill_sound()
                        self._fire("app_killed", {"app_id": app_id, "name": app_name,
                                                  "limit_min": daily_limit_min})
                        return  # process is gone; poll will handle session end

                # Notify (once per over-limit event)
                if f"{app_id}_over" not in self._notified_limits:
                    self._notified_limits.add(f"{app_id}_over")
                    if self.config.get("notifications_enabled", True):
                        mins_used = today_sec // 60
                        _send_notification(
                            "FocusGuard — Limit Reached",
                            f"{app_name} has exceeded its daily limit of {daily_limit_min} min "
                            f"(used {mins_used} min today).",
                            sound=self.config.get("notification_sound", False),
                        )
                    self._fire("limit_exceeded", {"app_id": app_id, "name": app_name,
                                                  "usage_pct": usage_pct})

            elif usage_pct >= warn_pct and notify_key not in self._notified_limits:
                self._notified_limits.add(notify_key)
                if self.config.get("notifications_enabled", True):
                    mins_remaining = max(0, (limit_sec - today_sec) // 60)
                    _send_notification(
                        "FocusGuard — Approaching Limit",
                        f"{app_name} — {int(usage_pct)}% of daily limit used. "
                        f"~{mins_remaining} min remaining.",
                        sound=self.config.get("notification_sound", False),
                    )
        except Exception:
            pass

    def _fire(self, event_type: str, data: dict) -> None:
        """Call all registered callbacks."""
        for fn in list(self.callbacks):
            try:
                fn(event_type, data)
            except Exception:
                pass
