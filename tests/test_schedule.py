"""
Focus hours (ROADMAP #7).

The overnight-window cases are the point of this file: a naive
`start <= now <= end` is False for every minute of a 22:00–06:00 block, which
is exactly the schedule someone setting an evening cutoff would configure.
"""

from datetime import datetime

import pytest

from core import schedule
from core.monitor import Monitor


def at(year=2026, month=6, day=15, hour=12, minute=0):
    """2026-06-15 is a Monday, so weekday() == 0."""
    return datetime(year, month, day, hour, minute)


@pytest.fixture
def focus(config):
    config.set("focus_hours_enabled", True)
    config.set("focus_hours_days", [0, 1, 2, 3, 4])     # Mon-Fri
    config.set("focus_hours_start", "09:00")
    config.set("focus_hours_end", "17:00")
    config.set("focus_hours_limit_min", 0)
    return config


# ── Time parsing ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("09:00", (9, 0)),
    ("00:00", (0, 0)),
    ("23:59", (23, 59)),
    ("9:5", (9, 5)),
])
def test_valid_times_parse(value, expected):
    assert schedule.parse_time(value) == expected


@pytest.mark.parametrize("value", ["", "banana", "25:00", "12:99", None, "12"])
def test_invalid_times_fall_back(value):
    """A mistyped setting must not take the monitor thread down."""
    assert schedule.parse_time(value, fallback=(8, 30)) == (8, 30)


def test_format_round_trips():
    assert schedule.format_time(*schedule.parse_time("07:05")) == "07:05"


# ── A normal daytime window ───────────────────────────────────────────────────

def test_inside_the_window_is_active(focus):
    assert schedule.is_active(focus, at(hour=10)) is True


def test_before_the_window_is_not_active(focus):
    assert schedule.is_active(focus, at(hour=8, minute=59)) is False


def test_the_start_minute_is_inside(focus):
    assert schedule.is_active(focus, at(hour=9, minute=0)) is True


def test_the_end_minute_is_outside(focus):
    """Ending at 17:00 means 17:00 itself is free."""
    assert schedule.is_active(focus, at(hour=17, minute=0)) is False
    assert schedule.is_active(focus, at(hour=16, minute=59)) is True


def test_a_day_outside_the_schedule_is_not_active(focus):
    saturday = at(day=20, hour=10)       # 2026-06-20
    assert saturday.weekday() == 5
    assert schedule.is_active(focus, saturday) is False


def test_disabled_means_never_active(focus):
    focus.set("focus_hours_enabled", False)
    assert schedule.is_active(focus, at(hour=10)) is False


def test_no_days_selected_means_never_active(focus):
    focus.set("focus_hours_days", [])
    assert schedule.is_active(focus, at(hour=10)) is False


def test_a_zero_length_window_is_never_active(focus):
    """Reading start == end as 'all day' would lock someone out of everything."""
    focus.set("focus_hours_start", "09:00")
    focus.set("focus_hours_end", "09:00")
    assert schedule.is_active(focus, at(hour=9)) is False
    assert schedule.is_active(focus, at(hour=14)) is False


# ── Overnight windows ─────────────────────────────────────────────────────────

@pytest.fixture
def overnight(focus):
    focus.set("focus_hours_start", "22:00")
    focus.set("focus_hours_end", "06:00")
    return focus


def test_late_evening_is_inside_an_overnight_window(overnight):
    assert schedule.is_active(overnight, at(hour=23)) is True


def test_after_midnight_is_inside_an_overnight_window(overnight):
    """A naive start <= now <= end is False here. That is the bug."""
    tuesday_early = at(day=16, hour=2)
    assert tuesday_early.weekday() == 1
    assert schedule.is_active(overnight, tuesday_early) is True


def test_the_middle_of_the_day_is_outside_an_overnight_window(overnight):
    assert schedule.is_active(overnight, at(hour=13)) is False


def test_early_morning_after_the_window_is_outside(overnight):
    assert schedule.is_active(overnight, at(day=16, hour=7)) is False


def test_a_friday_night_block_still_applies_on_saturday_morning(overnight):
    """
    The window belongs to the day it STARTED on. Friday 22:00 to Saturday 06:00
    is a Friday block, even though the clock says Saturday at 01:00.
    """
    overnight.set("focus_hours_days", [4])          # Friday only
    friday_night = at(day=19, hour=23)
    saturday_early = at(day=20, hour=1)
    assert friday_night.weekday() == 4
    assert saturday_early.weekday() == 5

    assert schedule.is_active(overnight, friday_night) is True
    assert schedule.is_active(overnight, saturday_early) is True


def test_a_saturday_block_does_not_leak_into_saturday_morning(overnight):
    overnight.set("focus_hours_days", [5])          # Saturday only
    saturday_early = at(day=20, hour=1)
    assert schedule.is_active(overnight, saturday_early) is False
    assert schedule.is_active(overnight, at(day=20, hour=23)) is True


def test_the_week_wraps_from_sunday_to_monday(overnight):
    overnight.set("focus_hours_days", [6])          # Sunday only
    monday_early = at(day=22, hour=2)
    assert monday_early.weekday() == 0
    assert schedule.is_active(overnight, monday_early) is True


# ── Effective limits ──────────────────────────────────────────────────────────

def limited(minutes):
    return {"name": "Chrome", "daily_limit_min": minutes}


def test_an_app_with_no_limit_is_untouched(focus):
    """
    The user never asked for this app to be limited. Silently restricting it
    during a window configured for something else would be a nasty surprise.
    """
    assert schedule.effective_daily_limit(limited(0), focus, at(hour=10)) == 0


def test_outside_focus_hours_the_apps_own_limit_applies(focus):
    assert schedule.effective_daily_limit(limited(60), focus, at(hour=20)) == 60


def test_a_zero_focus_cap_blocks_outright(focus):
    assert schedule.effective_daily_limit(limited(60), focus, at(hour=10)) == -1


def test_a_focus_cap_tightens_the_limit(focus):
    focus.set("focus_hours_limit_min", 15)
    assert schedule.effective_daily_limit(limited(60), focus, at(hour=10)) == 15


def test_focus_hours_can_only_tighten_never_loosen(focus):
    """A schedule that quietly raised a limit would defeat the point of it."""
    focus.set("focus_hours_limit_min", 120)
    assert schedule.effective_daily_limit(limited(30), focus, at(hour=10)) == 30


def test_a_garbage_focus_cap_falls_back_to_the_apps_own_limit(focus):
    focus.set("focus_hours_limit_min", "not a number")
    assert schedule.effective_daily_limit(limited(45), focus, at(hour=10)) == 45


# ── The monitor uses it ───────────────────────────────────────────────────────

def test_the_monitor_applies_focus_hours(db, focus, monkeypatch):
    monitor = Monitor(db, focus)
    focus.set("focus_hours_limit_min", 10)
    monkeypatch.setattr(schedule, "is_active", lambda *_a, **_kw: True)
    assert monitor._limit_for(limited(60)) == 10


def test_the_monitor_falls_back_when_focus_hours_are_off(db, focus, monkeypatch):
    monitor = Monitor(db, focus)
    monkeypatch.setattr(schedule, "is_active", lambda *_a, **_kw: False)
    assert monitor._limit_for(limited(60)) == 60


def test_zero_means_unlimited_and_minus_one_means_blocked(db, config):
    monitor = Monitor(db, config)
    assert monitor._limit_is_active(0) is False
    assert monitor._limit_is_active(60) is True
    assert monitor._limit_is_active(-1) is True

    assert monitor._limit_seconds(60) == 3600
    assert monitor._limit_seconds(0) == 0
    assert monitor._limit_seconds(-1) == 0, "blocked must allow no time at all"


def test_a_broken_schedule_does_not_break_limits(db, config, monkeypatch):
    """The monitor must survive anything the schedule module throws."""
    monitor = Monitor(db, config)

    def boom(*_a, **_kw):
        raise RuntimeError("bad config")

    monkeypatch.setattr(schedule, "effective_daily_limit", boom)
    assert monitor._limit_for(limited(45)) == 45


# ── Description ───────────────────────────────────────────────────────────────

def test_describe_reports_off_when_disabled(config):
    assert schedule.describe(config) == "Off"


def test_describe_lists_the_schedule(focus):
    text = schedule.describe(focus)
    assert "Mon" in text and "Fri" in text
    assert "09:00" in text and "17:00" in text
    assert "blocked" in text


def test_describe_reports_a_cap(focus):
    focus.set("focus_hours_limit_min", 20)
    assert "20 min" in schedule.describe(focus)
