"""
Usage accounting rules (AUDIT SF-05).

counted_seconds() is where the laptop-lid bug lived: elapsed wall-clock time
was credited unconditionally, so a machine asleep overnight booked eight hours
of "usage" and the app was closed on resume. These are pure-function tests —
no clock, no display, no Windows.
"""

import pytest

from core.activity import (
    DEFAULT_IDLE_THRESHOLD_SEC,
    SLEEP_GAP_FACTOR,
    UNKNOWN,
    counted_seconds,
    get_foreground_exe,
    get_idle_seconds,
    was_asleep,
)

POLL = 60


def counted(wall, **kw):
    kw.setdefault("require_foreground", False)
    return counted_seconds(wall, POLL, **kw)


# ── Normal accounting ─────────────────────────────────────────────────────────

def test_a_normal_interval_counts_in_full():
    assert counted(60) == 60


def test_a_short_interval_counts_in_full():
    assert counted(12) == 12


def test_zero_counts_as_nothing():
    assert counted(0) == 0


def test_a_backwards_clock_counts_as_nothing():
    """A DST change or a manual clock change must not produce negative usage."""
    assert counted(-3600) == 0


# ── Sleep and stalls (the laptop-lid bug) ─────────────────────────────────────

def test_an_overnight_gap_credits_only_one_interval():
    eight_hours = 8 * 60 * 60
    assert counted(eight_hours) == int(POLL * SLEEP_GAP_FACTOR)


def test_a_long_gap_is_recognised_as_sleep():
    assert was_asleep(8 * 60 * 60, POLL) is True


def test_a_normal_gap_is_not_sleep():
    assert was_asleep(60, POLL) is False
    assert was_asleep(75, POLL) is False


def test_a_small_overrun_is_tolerated():
    """A slightly slow poll is normal scheduling jitter, not a sleep."""
    assert counted(70) == 70


def test_the_cap_scales_with_the_poll_interval():
    assert counted_seconds(10_000, 300, require_foreground=False) == int(300 * SLEEP_GAP_FACTOR)


# ── Idle detection ────────────────────────────────────────────────────────────

def test_nothing_counts_while_the_user_is_away():
    assert counted(60, idle_seconds=DEFAULT_IDLE_THRESHOLD_SEC + 1) == 0


def test_time_counts_while_the_user_is_active():
    assert counted(60, idle_seconds=5) == 60


def test_the_idle_threshold_is_configurable():
    assert counted(60, idle_seconds=90, idle_threshold_sec=60) == 0
    assert counted(60, idle_seconds=30, idle_threshold_sec=60) == 60


def test_unknown_idle_time_counts_rather_than_silently_dropping():
    """Under-reporting invisibly is worse than crediting a minute."""
    assert counted(60, idle_seconds=UNKNOWN) == 60


# ── Foreground tracking ───────────────────────────────────────────────────────

def test_background_apps_do_not_accrue_when_foreground_is_required():
    assert counted_seconds(60, POLL, is_foreground=False,
                           require_foreground=True) == 0


def test_the_foreground_app_accrues():
    assert counted_seconds(60, POLL, is_foreground=True,
                           require_foreground=True) == 60


def test_background_apps_accrue_when_foreground_tracking_is_off():
    assert counted_seconds(60, POLL, is_foreground=False,
                           require_foreground=False) == 60


def test_unknown_foreground_counts():
    assert counted_seconds(60, POLL, is_foreground=None,
                           require_foreground=True) == 60


# ── Rules combine ─────────────────────────────────────────────────────────────

def test_idle_beats_foreground():
    """Sitting in front of an app you are not touching is not usage."""
    assert counted_seconds(60, POLL, is_foreground=True, idle_seconds=9999,
                           require_foreground=True) == 0


def test_sleep_cap_applies_before_the_other_rules():
    assert counted_seconds(99999, POLL, is_foreground=True, idle_seconds=0,
                           require_foreground=True) == int(POLL * SLEEP_GAP_FACTOR)


# ── OS probes degrade safely ──────────────────────────────────────────────────

def test_probes_never_raise_off_windows():
    """They are called every poll; an exception would kill the monitor thread."""
    assert isinstance(get_idle_seconds(), float)
    assert isinstance(get_foreground_exe(), str)


@pytest.mark.parametrize("wall", [0.5, 1, 59, 60, 61])
def test_result_is_always_a_non_negative_int(wall):
    result = counted(wall)
    assert isinstance(result, int)
    assert result >= 0
