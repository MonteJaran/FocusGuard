"""
The polling loop, against a faked psutil (AUDIT SF-04, SF-05).

No real processes are started and no real time passes: the process list, the
clock and the activity probes are all injected, so a session running past
midnight or a machine sleeping overnight can be reproduced exactly.
"""

from datetime import date, datetime, timedelta

import pytest

from core import activity, database as database_mod, monitor as monitor_mod
from core.config import Config
from core.database import Database
from core.monitor import Monitor


class FakeProc:
    def __init__(self, name, exe=""):
        self.info = {"name": name, "exe": exe}


# Module level: `X = X` inside a class body resolves in the class scope and
# raises NameError, so these cannot be nested in the factory below.
class _NoSuchProcess(Exception):
    pass


class _AccessDenied(Exception):
    pass


class Harness:
    """Owns the fakes so a test can drive the monitor a poll at a time."""

    def __init__(self, db, config, monkeypatch):
        self.db = db
        self.config = config
        self.monkeypatch = monkeypatch
        self.running = []
        self.now = datetime(2026, 6, 15, 10, 0, 0)
        self.clock = 1000.0
        self.foreground = ""
        self.idle = activity.UNKNOWN

        self.monitor = Monitor(db, config)
        self.events = []
        self.monitor.add_callback(lambda k, d: self.events.append((k, d)))

        monkeypatch.setattr(monitor_mod, "_PSUTIL_AVAILABLE", True)
        monkeypatch.setattr(monitor_mod, "psutil", self._fake_psutil())
        monkeypatch.setattr(monitor_mod.activity, "get_foreground_exe",
                            lambda: self.foreground)
        monkeypatch.setattr(monitor_mod.activity, "get_idle_seconds",
                            lambda: self.idle)
        monkeypatch.setattr(monitor_mod.time, "monotonic", lambda: self.clock)
        monkeypatch.setattr(monitor_mod, "datetime", self._fake_datetime())
        # The database decides "today" independently via date.today(). Without
        # faking that too, the monitor lives on the fake clock while every
        # date-filtered query still uses the real one, and they disagree.
        monkeypatch.setattr(database_mod, "date", self._fake_date())
        monkeypatch.setattr(monitor_mod, "_send_notification",
                            lambda *_a, **_kw: None)

    def _fake_psutil(self):
        harness = self

        class FakePsutil:
            NoSuchProcess = _NoSuchProcess
            AccessDenied = _AccessDenied

            @staticmethod
            def process_iter(_attrs=None):
                return list(harness.running)

        return FakePsutil

    def _fake_datetime(self):
        harness = self

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return harness.now

        return FakeDatetime

    def _fake_date(self):
        harness = self

        class FakeDate(date):
            @classmethod
            def today(cls):
                return harness.now.date()

        return FakeDate

    def launch(self, exe_name):
        self.running.append(FakeProc(exe_name))

    def quit_app(self, exe_name):
        self.running = [p for p in self.running
                        if p.info["name"].lower() != exe_name.lower()]

    def advance(self, seconds):
        """Move both the wall clock and the monotonic clock forward."""
        self.now = self.now + timedelta(seconds=seconds)
        self.clock += seconds

    def poll(self):
        self.monitor._poll()

    def session(self, app_id):
        return self.monitor.active_sessions.get(app_id)


@pytest.fixture
def harness(data_dir, monkeypatch):
    db = Database(data_dir=data_dir)
    config = Config(data_dir=data_dir)
    config.set("poll_interval", 60)
    config.set("count_foreground_only", False)
    h = Harness(db, config, monkeypatch)
    yield h
    db.close()


# ── Basic session lifecycle ───────────────────────────────────────────────────

def test_a_running_app_opens_a_session(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()
    assert harness.session(app_id) is not None


def test_a_closed_app_ends_its_session(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()
    harness.advance(60)
    harness.poll()
    harness.quit_app("chrome.exe")
    harness.advance(60)
    harness.poll()

    assert harness.session(app_id) is None
    assert harness.db.get_today_usage_sec(app_id) == 60


def test_usage_accrues_across_polls(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()
    for _ in range(3):
        harness.advance(60)
        harness.poll()
    assert harness.session(app_id)["counted_sec"] == 180


def test_an_untracked_app_is_ignored(harness):
    harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("discord.exe")
    harness.poll()
    assert harness.monitor.active_sessions == {}


# ── The laptop-lid bug (SF-05) ────────────────────────────────────────────────

def test_an_overnight_sleep_does_not_book_eight_hours(harness):
    """
    Was: shut the lid with Chrome open, resume, and FocusGuard had booked the
    whole night as usage and closed Chrome immediately.
    """
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()

    harness.advance(8 * 60 * 60)      # lid shut overnight
    harness.poll()

    counted = harness.session(app_id)["counted_sec"]
    assert counted <= 90, f"credited {counted}s for an overnight sleep"


def test_idle_time_does_not_count(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()

    harness.idle = 9999               # user away from the keyboard
    harness.advance(60)
    harness.poll()

    assert harness.session(app_id)["counted_sec"] == 0


def test_background_apps_do_not_count_when_foreground_tracking_is_on(harness):
    harness.config.set("count_foreground_only", True)
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.foreground = "code.exe"   # user is working elsewhere
    harness.poll()
    harness.advance(60)
    harness.poll()

    assert harness.session(app_id)["counted_sec"] == 0


def test_the_foreground_app_counts(harness):
    harness.config.set("count_foreground_only", True)
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.foreground = "chrome.exe"
    harness.poll()
    harness.advance(60)
    harness.poll()

    assert harness.session(app_id)["counted_sec"] == 60


# ── The midnight boundary (SF-04) ─────────────────────────────────────────────

def test_a_session_running_past_midnight_is_split(harness):
    """
    Was: a session opened at 23:50 filed its entire run under the start date,
    and get_today_usage_sec (which filters on date = today) stopped seeing it,
    so the daily counter silently reset mid-session.
    """
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.now = datetime(2026, 6, 15, 23, 50, 0)
    harness.launch("chrome.exe")
    harness.poll()

    harness.advance(60)               # 23:51
    harness.poll()
    assert harness.session(app_id)["date"] == date(2026, 6, 15)

    harness.advance(20 * 60)          # 00:11 the next day
    harness.poll()

    session = harness.session(app_id)
    assert session is not None, "the app is still running; a session must exist"
    assert session["date"] == date(2026, 6, 16)


def test_yesterdays_usage_stays_on_yesterday(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.now = datetime(2026, 6, 15, 23, 50, 0)
    harness.launch("chrome.exe")
    harness.poll()
    harness.advance(60)
    harness.poll()                    # 60s of usage on the 15th

    harness.advance(20 * 60)          # crosses midnight
    harness.poll()

    history = {h["date"]: h["total_sec"]
               for h in harness.db.get_usage_history(app_id, days=5)}
    assert history.get("2026-06-15") == 60


def test_the_new_day_does_not_inherit_yesterdays_total(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.now = datetime(2026, 6, 15, 23, 50, 0)
    harness.launch("chrome.exe")
    harness.poll()
    harness.advance(60)
    harness.poll()                    # 60s booked on the 15th

    harness.advance(20 * 60)          # crosses midnight; capped at 90s
    harness.poll()
    harness.advance(60)               # a normal minute on the 16th
    harness.poll()

    # 90 (the capped straddling interval) + 60. Critically, NOT 210 — the 60
    # seconds booked on the 15th stay on the 15th.
    assert harness.session(app_id)["counted_sec"] == 150

    history = {h["date"]: h["total_sec"]
               for h in harness.db.get_usage_history(app_id, days=5)}
    assert history["2026-06-15"] == 60


def test_no_split_within_the_same_day(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()
    first = harness.session(app_id)["session_id"]

    harness.advance(60)
    harness.poll()
    assert harness.session(app_id)["session_id"] == first


# ── Limits read live numbers ──────────────────────────────────────────────────

def test_the_limit_check_sees_uncheckpointed_time(harness):
    """
    The database lags by up to a poll interval, so the limit must be judged
    against counted_sec, not only what has been written.
    """
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.db.set_app_limits(app_id, 2, 0)      # 2 minutes
    harness.launch("chrome.exe")
    harness.poll()
    harness.advance(60)
    harness.poll()

    session = harness.session(app_id)
    session["counted_sec"] = 300                 # well past the limit
    assert harness.monitor._usage_today_sec(app_id) >= 300


def test_usage_today_matches_the_database_with_no_live_session(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    stamp = harness.now.isoformat()
    harness.db.end_session(harness.db.start_session(app_id, stamp), stamp, 450)
    assert harness.monitor._usage_today_sec(app_id) == 450


def test_status_snapshot_reports_running_apps(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.launch("chrome.exe")
    harness.poll()
    status = harness.monitor.get_status()
    assert status[app_id]["running"] is True


# ── Robustness ────────────────────────────────────────────────────────────────

def test_apps_with_no_executable_are_skipped(harness):
    harness.db.add_tracked_app("Broken", "", "")
    harness.poll()
    assert harness.monitor.active_sessions == {}


def test_disabled_apps_are_not_tracked(harness):
    app_id = harness.db.add_tracked_app("Chrome", "chrome.exe")
    harness.db.set_app_enabled(app_id, False)
    harness.launch("chrome.exe")
    harness.poll()
    assert harness.monitor.active_sessions == {}


def test_polling_with_nothing_tracked_is_harmless(harness):
    harness.poll()
    assert harness.monitor.active_sessions == {}
