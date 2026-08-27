"""
monitor.py - Background monitoring thread for FocusGuard.
"""

import threading
import time
from datetime import datetime, timedelta

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    # Bind the name even when unavailable, so every reference below is a
    # simple attribute lookup rather than a NameError waiting to happen.
    psutil = None
    _PSUTIL_AVAILABLE = False

from core import activity, procutil
from core.logging_setup import get_logger
from core.protected import is_protected

log = get_logger("monitor")

# How long the user gets between "you have hit your limit" and the app being
# closed. Gives them time to save. Overridable via the close_grace_seconds
# config key; never drops below this floor.
MIN_GRACE_SECONDS = 10
DEFAULT_GRACE_SECONDS = 60

# Optional notification support
def _send_notification(title: str, message: str) -> None:
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

        # Guards active_sessions / running_apps / _notified_limits, all of
        # which are touched by the monitor thread, the kill watcher and the UI.
        self._lock = threading.RLock()

        # Cache to avoid notifying the same limit breach repeatedly
        self._notified_limits = set()  # app_ids already warned today
        # The day _notified_limits refers to, so warnings resume after midnight
        self._notified_day = datetime.now().date()
        # app_id -> datetime after which the app may be closed. Set when the
        # limit is first hit so the user gets a warning before anything closes.
        self._close_deadlines = {}
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
        with self._lock:
            sessions = list(self.active_sessions.items())
        for _app_id, session in sessions:
            try:
                self.db.end_session(session["session_id"], now.isoformat(),
                                    int(session["counted_sec"]))
            except Exception as e:
                log.error("Could not end session on stop: %s", e)
        with self._lock:
            self.active_sessions.clear()
            self.running_apps.clear()
        for thread in (self._thread, self._kill_thread):
            if thread:
                thread.join(timeout=5)

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
            with self._lock:
                running = set(self.running_apps)
            for app in apps:
                app_id = app["id"]
                result[app_id] = {
                    "running": app_id in running,
                    "today_sec": self._usage_today_sec(app_id),
                    "week_sec": self.db.get_week_usage_sec(app_id),
                }
        except Exception as e:
            log.error("Could not build status snapshot: %s", e)
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def trigger_poll(self) -> None:
        """Wake up the monitor thread to do an immediate poll."""
        self._poll_now.set()

    def _log(self, msg: str) -> None:
        """Per-poll detail. DEBUG so it is off unless someone is debugging."""
        log.debug(msg)

    def _run(self) -> None:
        """Main monitor loop."""
        self._log(f"Monitor thread started. psutil_available={_PSUTIL_AVAILABLE}")
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                self.last_poll_error = str(e)
                log.exception("Poll failed: %s", e)
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
            self._reset_daily_state_if_needed()
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
                    today_sec = self._usage_today_sec(app_id)

                    if today_sec >= daily_limit * 60:
                        # Warns and starts a grace period on the first pass;
                        # only closes once that deadline has passed.
                        if not self._due_to_close(app_id, app["name"], daily_limit):
                            continue
                        closed = self._close_app(app["name"], exe_name, exe_path)
                        if closed:
                            self._clear_close_deadline(app_id)
                            if self.config.get("notifications_enabled", True):
                                _send_notification(
                                    "FocusGuard — App Closed",
                                    f"{app['name']} was closed: daily limit of "
                                    f"{daily_limit} min reached.",
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
        self._reset_daily_state_if_needed()
        running_names, running_paths = self._get_running_info()
        self.last_poll_time = datetime.now()
        self.last_poll_proc_count = len(running_names)
        self._log(f"Poll: {len(running_names)} processes found. "
                  f"Tracking {len(self.db.get_all_tracked_apps())} apps.")

        apps = self.db.get_all_tracked_apps()
        enabled_apps = [a for a in apps if a.get("enabled", 1)]

        now = datetime.now()
        changed = False

        # Sampled once per poll rather than per app: both are OS calls, and
        # every app in this pass is being judged against the same instant.
        foreground_exe = activity.get_foreground_exe()
        idle_seconds = activity.get_idle_seconds()

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
                    # No grace period here: the app has only just launched, so
                    # there is nothing unsaved to lose. It is still closed
                    # politely rather than terminated.
                    self._log(f"'{app['name']}' launched but already over limit — closing.")
                    closed = self._close_app(app["name"], exe_name, exe_path)
                    if closed:
                        if self.config.get("notifications_enabled", True):
                            _send_notification(
                                "FocusGuard — App Blocked",
                                f"{app['name']} was blocked: you have already reached "
                                f"your daily limit of {app.get('daily_limit_min', 0)} min.",
                            )
                        if self.config.get("notification_sound", False):
                            _play_kill_sound()
                        self._fire("app_killed", {"app_id": app_id, "name": app["name"],
                                                  "limit_min": app.get("daily_limit_min", 0)})
                        continue  # don't start a session for it

                try:
                    session_id = self.db.start_session(app_id, now.isoformat())
                    with self._lock:
                        self.active_sessions[app_id] = self._new_session(
                            session_id, now)
                        self.running_apps.add(app_id)
                    changed = True
                    self._fire("app_started", {"app_id": app_id, "name": app["name"]})
                except Exception as e:
                    log.error("Could not start session for '%s': %s",
                              app["name"], e)

            elif not is_running and app_id in self.active_sessions:
                # App just stopped
                with self._lock:
                    session = self.active_sessions.pop(app_id)
                    self.running_apps.discard(app_id)
                changed = True
                try:
                    self.db.end_session(session["session_id"], now.isoformat(),
                                        int(session["counted_sec"]))
                    self._fire("app_stopped", {"app_id": app_id, "name": app["name"]})
                    # Clear limit notification cache on stop so it can warn again next run
                    with self._lock:
                        self._notified_limits.discard(app_id)
                except Exception as e:
                    log.error("Could not end session for '%s': %s", app["name"], e)

            elif is_running and app_id in self.active_sessions:
                with self._lock:
                    session = self.active_sessions.get(app_id)
                if session is None:
                    continue

                # Split BEFORE crediting. The interval that straddles midnight
                # is credited to the new day, because crediting it first would
                # file time earned after midnight under yesterday's date.
                if self._split_at_midnight(app_id, app, session, now):
                    changed = True
                    with self._lock:
                        session = self.active_sessions.get(app_id)
                    if session is None:
                        continue

                # Credit this interval before anything reads the total, so the
                # limit check sees current numbers.
                credited = self._accrue(app, session, foreground_exe, idle_seconds)
                self._log(f"  '{app['name']}': credited {credited}s "
                          f"(total {session['counted_sec']}s)")

                daily_limit = app.get("daily_limit_min", 0)
                if daily_limit and daily_limit > 0:
                    self._check_limits(app_id, app["name"], exe_name, exe_path, daily_limit)

        # Save progress for all still-running sessions so data survives crashes
        with self._lock:
            open_sessions = list(self.active_sessions.items())
        for _app_id, session in open_sessions:
            try:
                counted = int(session["counted_sec"])
                self.db.update_session_duration(session["session_id"], counted)
                session["written_sec"] = counted
            except Exception as e:
                log.error("Could not checkpoint session: %s", e)

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

    # ── Usage accounting ──────────────────────────────────────────────────────

    def _new_session(self, session_id: int, now: datetime) -> dict:
        """
        A session record.

        `counted_sec` is the accumulated *counted* usage, not wall-clock time
        since start: time while the machine was asleep, or while the user was
        away, or while the app sat in a background window, does not go in here.
        `tick` is a monotonic timestamp so the accounting cannot be skewed by
        DST or the user changing the clock.
        """
        return {
            "session_id": session_id,
            "start_time": now,
            "date": now.date(),
            "counted_sec": 0,     # accrued so far
            "written_sec": 0,     # how much of that is already in the database
            "tick": time.monotonic(),
        }

    def _accrue(self, app: dict, session: dict, foreground_exe: str,
                idle_seconds: float) -> int:
        """
        Add this interval's counted usage to a running session.

        Returns the number of seconds credited, which may be zero.
        """
        now_tick = time.monotonic()
        wall = now_tick - session["tick"]
        session["tick"] = now_tick

        poll_interval = self.config.get("poll_interval", 60) or 60
        exe_name = (app.get("exe_name") or "").lower().strip()

        is_foreground = None
        if foreground_exe:
            is_foreground = bool(exe_name) and foreground_exe == exe_name

        if activity.was_asleep(wall, poll_interval):
            log.info("Gap of %.0fs since last tick for '%s' — machine was "
                     "asleep or stalled; crediting one interval at most.",
                     wall, app.get("name", "?"))

        credited = activity.counted_seconds(
            wall,
            poll_interval,
            is_foreground=is_foreground,
            idle_seconds=idle_seconds,
            require_foreground=bool(self.config.get("count_foreground_only", True)),
            idle_threshold_sec=self.config.get(
                "idle_threshold_sec", activity.DEFAULT_IDLE_THRESHOLD_SEC),
        )
        session["counted_sec"] += credited
        return credited

    def _split_at_midnight(self, app_id: int, app: dict, session: dict,
                           now: datetime) -> bool:
        """
        Close a session that has run past midnight and open a fresh one.

        Without this, a session started at 23:50 keeps filing its whole run
        under yesterday's date, and get_today_usage_sec() — which filters on
        date = today — stops seeing it entirely, so the daily counter silently
        resets to zero mid-session.

        Returns True if the session was rolled over.
        """
        if session["date"] == now.date():
            return False

        boundary = datetime.combine(session["date"], datetime.max.time())
        try:
            self.db.end_session(session["session_id"], boundary.isoformat(),
                                int(session["counted_sec"]))
            new_id = self.db.start_session(app_id, now.isoformat())
        except Exception as e:
            log.error("Could not split session for '%s' at midnight: %s",
                      app.get("name", "?"), e)
            return False

        log.info("'%s' ran past midnight — filed %ds under %s and started a "
                 "new session for %s.", app.get("name", "?"),
                 int(session["counted_sec"]), session["date"], now.date())

        with self._lock:
            fresh = self._new_session(new_id, now)
            fresh["tick"] = session["tick"]   # keep accounting continuous
            self.active_sessions[app_id] = fresh
        return True

    def _usage_today_sec(self, app_id: int) -> int:
        """
        Today's usage, including what the running session has accrued since the
        last checkpoint.

        The database already holds everything up to `written_sec`; anything
        beyond that is in memory only, so the un-checkpointed remainder is what
        gets added. Without this the limit check lags by up to a poll interval.
        """
        total = self.db.get_today_usage_sec(app_id)
        with self._lock:
            session = self.active_sessions.get(app_id)
            if session and session["date"] == datetime.now().date():
                total += max(0, session["counted_sec"] - session["written_sec"])
        return int(total)

    def _grace_seconds(self) -> int:
        """Warning period before an over-limit app is closed."""
        try:
            configured = int(self.config.get("close_grace_seconds",
                                             DEFAULT_GRACE_SECONDS))
        except (TypeError, ValueError):
            configured = DEFAULT_GRACE_SECONDS
        return max(MIN_GRACE_SECONDS, configured)

    def _close_app(self, app_name: str, exe_name: str, exe_path: str) -> bool:
        """
        Close every process matching this app, giving it a chance to save.

        Posts WM_CLOSE first so the application runs its own save-and-exit
        path, waits, and only terminates what refuses to go. Returns True if
        the app is gone afterwards. See core/procutil.py.
        """
        if not _PSUTIL_AVAILABLE:
            return False
        if is_protected(exe_name, exe_path):
            self._log(f"Refusing to close protected process for '{app_name}'.")
            return False
        try:
            result = procutil.close_app(exe_name, exe_path, log=self._log)
        except Exception as e:
            self._log(f"Error closing {app_name}: {e}")
            return False

        if result["matched"]:
            self._log(
                f"Closed '{app_name}': matched={result['matched']} "
                f"asked={result['asked']} forced={result['forced']}"
            )
        return result["closed"]

    def _due_to_close(self, app_id: int, app_name: str, daily_limit_min: int) -> bool:
        """
        Decide whether an over-limit app may be closed yet.

        The first time an app goes over, this starts a grace period and warns
        the user instead of closing anything. Only once that deadline passes
        does it return True. Without this the app is terminated the instant the
        limit is crossed, with no chance to save.
        """
        now = datetime.now()
        with self._lock:
            deadline = self._close_deadlines.get(app_id)
            if deadline is None:
                grace = self._grace_seconds()
                self._close_deadlines[app_id] = now + timedelta(seconds=grace)
                warn = True
            else:
                warn = False

        if warn:
            self._log(f"'{app_name}' over limit — warning, closing in "
                      f"{self._grace_seconds()}s.")
            if self.config.get("notifications_enabled", True):
                _send_notification(
                    "FocusGuard — Save your work",
                    f"{app_name} has reached its daily limit of "
                    f"{daily_limit_min} min and will close in "
                    f"{self._grace_seconds()} seconds.",
                )
            if self.config.get("notification_sound", False):
                _play_kill_sound()
            self._fire("close_pending", {
                "app_id": app_id,
                "name": app_name,
                "limit_min": daily_limit_min,
                "seconds": self._grace_seconds(),
            })
            return False

        return now >= deadline

    def _clear_close_deadline(self, app_id: int) -> None:
        with self._lock:
            self._close_deadlines.pop(app_id, None)

    def _reset_daily_state_if_needed(self) -> None:
        """
        Clear per-day caches when the date rolls over.

        Without this, _notified_limits keeps yesterday's entries forever and
        the user stops receiving warnings entirely after day one.
        """
        today = datetime.now().date()
        with self._lock:
            if today != self._notified_day:
                self._notified_day = today
                self._notified_limits.clear()
                self._close_deadlines.clear()
                self._log(f"Date rolled over to {today} — daily state reset.")

    def _is_over_daily_limit(self, app_id: int, app: dict) -> bool:
        """Return True if the app has already used up its daily limit."""
        daily_limit_min = app.get("daily_limit_min", 0) or 0
        if daily_limit_min <= 0:
            return False
        try:
            return self._usage_today_sec(app_id) >= daily_limit_min * 60
        except Exception as e:
            log.error("Could not read usage for app %s: %s", app_id, e)
            return False

    def _check_limits(self, app_id: int, app_name: str, exe_name: str,
                      exe_path: str, daily_limit_min: int) -> None:
        """Notify and optionally kill app if it has exceeded or is near its daily limit."""
        try:
            today_sec = self._usage_today_sec(app_id)

            limit_sec = daily_limit_min * 60
            warn_pct  = self.config.get("warn_at_percent", 80)
            usage_pct = (today_sec / limit_sec * 100) if limit_sec > 0 else 0

            notify_key = f"{app_id}_{int(usage_pct // 10) * 10}"

            if usage_pct >= 100:
                # Auto-close if enabled, after the user has had a warning and
                # the grace period has elapsed.
                if self.config.get("auto_kill_over_limit", False):
                    if not self._due_to_close(app_id, app_name, daily_limit_min):
                        return  # warned; give them time to save
                    closed = self._close_app(app_name, exe_name, exe_path)
                    if closed:
                        self._clear_close_deadline(app_id)
                        if self.config.get("notifications_enabled", True):
                            _send_notification(
                                "FocusGuard — App Closed",
                                f"{app_name} was closed automatically: daily limit of "
                                f"{daily_limit_min} min reached.",
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
                        )
                        if self.config.get("notification_sound", False):
                            _play_kill_sound()
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
                    )
                    if self.config.get("notification_sound", False):
                        _play_kill_sound()
        except Exception:
            pass

    def _fire(self, event_type: str, data: dict) -> None:
        """Call all registered callbacks."""
        for fn in list(self.callbacks):
            try:
                fn(event_type, data)
            except Exception:
                pass
