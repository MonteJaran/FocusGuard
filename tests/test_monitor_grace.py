"""
The warning grace period before an app is closed (AUDIT SF-01).

Closing the instant the limit is crossed is what destroys unsaved work. The
first time an app goes over it must warn and start a countdown; only after that
deadline may anything close.
"""

from datetime import datetime, timedelta

import pytest

from core.config import Config
from core.database import Database
from core.monitor import DEFAULT_GRACE_SECONDS, MIN_GRACE_SECONDS, Monitor


@pytest.fixture
def monitor(data_dir):
    db = Database(data_dir=data_dir)
    config = Config(data_dir=data_dir)
    mon = Monitor(db, config)
    events = []
    mon.add_callback(lambda kind, data: events.append((kind, data)))
    mon.events = events
    yield mon
    db.close()


def test_first_breach_warns_instead_of_closing(monitor):
    assert monitor._due_to_close(1, "Chrome", 60) is False


def test_first_breach_fires_a_close_pending_event(monitor):
    monitor._due_to_close(1, "Chrome", 60)
    kinds = [kind for kind, _ in monitor.events]
    assert "close_pending" in kinds

    _kind, data = next(e for e in monitor.events if e[0] == "close_pending")
    assert data["name"] == "Chrome"
    assert data["limit_min"] == 60
    assert data["seconds"] == DEFAULT_GRACE_SECONDS


def test_still_not_due_while_the_grace_period_is_running(monitor):
    monitor._due_to_close(1, "Chrome", 60)
    assert monitor._due_to_close(1, "Chrome", 60) is False


def test_due_once_the_deadline_passes(monitor):
    monitor._due_to_close(1, "Chrome", 60)
    monitor._close_deadlines[1] = datetime.now() - timedelta(seconds=1)
    assert monitor._due_to_close(1, "Chrome", 60) is True


def test_warning_fires_only_once_per_breach(monitor):
    for _ in range(5):
        monitor._due_to_close(1, "Chrome", 60)
    warnings = [e for e in monitor.events if e[0] == "close_pending"]
    assert len(warnings) == 1


def test_each_app_gets_its_own_deadline(monitor):
    monitor._due_to_close(1, "Chrome", 60)
    monitor._due_to_close(2, "Discord", 30)
    assert set(monitor._close_deadlines) == {1, 2}

    monitor._close_deadlines[1] = datetime.now() - timedelta(seconds=1)
    assert monitor._due_to_close(1, "Chrome", 60) is True
    assert monitor._due_to_close(2, "Discord", 30) is False


def test_clearing_a_deadline_re_arms_the_warning(monitor):
    monitor._due_to_close(1, "Chrome", 60)
    monitor._clear_close_deadline(1)
    assert monitor._due_to_close(1, "Chrome", 60) is False
    assert len([e for e in monitor.events if e[0] == "close_pending"]) == 2


# ── Grace period configuration ────────────────────────────────────────────────

def test_grace_period_defaults_to_a_minute(monitor):
    assert monitor._grace_seconds() == DEFAULT_GRACE_SECONDS


def test_grace_period_is_configurable(monitor):
    monitor.config.set("close_grace_seconds", 120)
    assert monitor._grace_seconds() == 120


def test_grace_period_cannot_be_set_to_zero(monitor):
    """A zero grace period is the bug this whole mechanism exists to prevent."""
    monitor.config.set("close_grace_seconds", 0)
    assert monitor._grace_seconds() == MIN_GRACE_SECONDS


def test_negative_grace_period_is_floored(monitor):
    monitor.config.set("close_grace_seconds", -99)
    assert monitor._grace_seconds() == MIN_GRACE_SECONDS


def test_garbage_grace_period_falls_back_to_the_default(monitor):
    monitor.config.set("close_grace_seconds", "not a number")
    assert monitor._grace_seconds() == DEFAULT_GRACE_SECONDS


# ── Protected processes ───────────────────────────────────────────────────────

def test_close_app_refuses_protected_processes(monitor):
    assert monitor._close_app("Task Manager", "taskmgr.exe", "") is False
    assert monitor._close_app("Windows", "csrss.exe", "") is False


# ── Daily rollover (AUDIT SF-14) ──────────────────────────────────────────────

def test_rollover_clears_yesterdays_warnings(monitor):
    """
    _notified_limits was never cleared, so warnings stopped firing entirely
    after day one until the app was restarted.
    """
    monitor._notified_limits.add("1_over")
    monitor._close_deadlines[1] = datetime.now()
    monitor._notified_day = (datetime.now() - timedelta(days=1)).date()

    monitor._reset_daily_state_if_needed()

    assert monitor._notified_limits == set()
    assert monitor._close_deadlines == {}
    assert monitor._notified_day == datetime.now().date()


def test_rollover_is_a_no_op_within_the_same_day(monitor):
    monitor._notified_limits.add("1_over")
    monitor._reset_daily_state_if_needed()
    assert monitor._notified_limits == {"1_over"}
