"""
schedule.py - Focus hours: a recurring window where limits tighten.

Scoped deliberately to ONE window rather than a full multi-block scheduler.
That covers the actual use case — work hours, study hours, evenings — and it
ships complete. A half-built multi-block editor would be a feature that exists
in the settings screen and nowhere else, which is the mistake this project
already made once (AUDIT BL-02).

## Semantics

During focus hours, every tracked app that **already has a daily limit** gets a
tighter one. Apps with no limit set are untouched: the user never asked for
those to be restricted, and silently restricting them during a window they
configured for something else would be a nasty surprise.

`focus_hours_limit_min = 0` means "not allowed at all while focusing".

## Overnight windows

22:00–06:00 is a normal thing to want and the classic place this kind of code
breaks: naive `start <= now <= end` is False for every minute of it. The window
is treated as wrapping whenever end <= start, and the day-of-week test then
applies to the day the window *started* on, so a Friday-night block still
applies at 01:00 on Saturday.
"""

from datetime import datetime

from core.logging_setup import get_logger

log = get_logger("schedule")

# 0 = Monday, matching datetime.weekday().
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DEFAULT_START = "09:00"
DEFAULT_END = "17:00"
DEFAULT_DAYS = [0, 1, 2, 3, 4]          # weekdays


def parse_time(value: str, fallback=(0, 0)) -> tuple:
    """
    "HH:MM" as (hour, minute). Returns `fallback` for anything unparseable —
    a mistyped setting must not take the monitor thread down.
    """
    try:
        hours, _, minutes = str(value).partition(":")
        hour, minute = int(hours), int(minutes)
    except (TypeError, ValueError):
        return fallback
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return fallback
    return hour, minute


def format_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _minutes(hour: int, minute: int) -> int:
    return hour * 60 + minute


def is_active(config, now: datetime = None) -> bool:
    """True if focus hours are in effect right now."""
    if not config.get("focus_hours_enabled", False):
        return False

    now = now or datetime.now()

    days = config.get("focus_hours_days", DEFAULT_DAYS)
    if not isinstance(days, (list, tuple)) or not days:
        return False
    days = {int(d) for d in days if isinstance(d, (int, float))}

    start = _minutes(*parse_time(config.get("focus_hours_start", DEFAULT_START),
                                 fallback=parse_time(DEFAULT_START)))
    end = _minutes(*parse_time(config.get("focus_hours_end", DEFAULT_END),
                               fallback=parse_time(DEFAULT_END)))
    current = _minutes(now.hour, now.minute)

    if start == end:
        # A zero-length window is almost certainly a mistake, and reading it as
        # "all day" would lock someone out of everything.
        return False

    if start < end:
        return now.weekday() in days and start <= current < end

    # Wraps midnight. Before `end` belongs to the window that began yesterday,
    # so the day check uses yesterday's weekday.
    if current >= start:
        return now.weekday() in days
    if current < end:
        return (now.weekday() - 1) % 7 in days
    return False


def effective_daily_limit(app: dict, config, now: datetime = None) -> int:
    """
    The daily limit to enforce for this app right now, in minutes.

    Outside focus hours this is the app's own limit. Inside them it is the
    tighter of the two — focus hours may only ever restrict further, never
    loosen, because a schedule that quietly *raised* someone's limit would
    defeat the point of setting one.
    """
    own = int(app.get("daily_limit_min", 0) or 0)

    # No limit set means the user did not ask for this app to be limited.
    if own <= 0:
        return 0

    if not is_active(config, now):
        return own

    try:
        focus = int(config.get("focus_hours_limit_min", 0) or 0)
    except (TypeError, ValueError):
        log.warning("focus_hours_limit_min is not a number; ignoring it.")
        return own

    if focus <= 0:
        return -1          # sentinel: not allowed at all while focusing
    return min(own, focus)


def describe(config) -> str:
    """One line describing the schedule, for the settings screen."""
    if not config.get("focus_hours_enabled", False):
        return "Off"

    days = config.get("focus_hours_days", DEFAULT_DAYS) or []
    day_text = ", ".join(DAY_NAMES[int(d)] for d in sorted(days)
                         if 0 <= int(d) <= 6) or "no days"

    start = config.get("focus_hours_start", DEFAULT_START)
    end = config.get("focus_hours_end", DEFAULT_END)

    try:
        limit = int(config.get("focus_hours_limit_min", 0) or 0)
    except (TypeError, ValueError):
        limit = 0
    limit_text = ("limited apps are blocked" if limit <= 0
                  else f"limited apps capped at {limit} min")

    return f"{day_text}  {start}–{end}  ({limit_text})"
