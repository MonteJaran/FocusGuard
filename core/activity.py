"""
activity.py - Deciding whether elapsed time actually counts as usage.

The original accounting was pure wall-clock: the gap between two polls was
added to the session, unconditionally. Two consequences, both bad:

  * Shut the laptop lid overnight with Chrome open and FocusGuard books eight
    hours of "usage", then closes Chrome the moment you resume.
  * An app sitting in a background window you never look at accrues time at the
    same rate as one you are actively working in.

The policy lives in counted_seconds(), which is a pure function so the rules
can be tested without Windows, a display, or a real clock. The two OS probes
below are thin and degrade to "cannot tell" everywhere else, in which case the
policy counts the time rather than silently under-reporting.
"""

import sys

_IS_WINDOWS = sys.platform == "win32"

# Treat the user as away after this long with no keyboard or mouse input.
DEFAULT_IDLE_THRESHOLD_SEC = 300

# A gap longer than this multiple of the poll interval means the process was
# not running normally — machine asleep, hibernated, or the thread was starved.
# Only the expected interval is credited, never the whole gap.
SLEEP_GAP_FACTOR = 1.5

UNKNOWN = -1.0


def get_idle_seconds() -> float:
    """
    Seconds since the last keyboard or mouse input, or UNKNOWN if it cannot be
    determined (non-Windows, or the call failed).
    """
    if not _IS_WINDOWS:
        return UNKNOWN
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return UNKNOWN
        millis_now = ctypes.windll.kernel32.GetTickCount()
        # GetTickCount wraps after ~49 days; a negative delta means it wrapped.
        delta = millis_now - info.dwTime
        if delta < 0:
            return UNKNOWN
        return delta / 1000.0
    except Exception:
        return UNKNOWN


def get_foreground_exe() -> str:
    """
    Lowercased executable name of the window the user is currently working in,
    or "" if it cannot be determined.
    """
    if not _IS_WINDOWS:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                      False, pid.value)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf,
                                                       ctypes.byref(size)):
                return ""
            return buf.value.replace("\\", "/").rsplit("/", 1)[-1].lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""


def counted_seconds(
    wall_seconds: float,
    poll_interval: float,
    *,
    is_foreground=None,
    idle_seconds: float = UNKNOWN,
    require_foreground: bool = True,
    idle_threshold_sec: float = DEFAULT_IDLE_THRESHOLD_SEC,
) -> int:
    """
    How many of `wall_seconds` count as real usage.

    Rules, in order:
      * A negative or zero gap counts as nothing (clock changes, DST).
      * A gap much longer than the poll interval means the machine was asleep,
        so only the expected interval is credited — never the whole gap.
      * If the user has been idle past the threshold, nothing counts.
      * If foreground tracking is on and this app is not the foreground app,
        nothing counts.

    `is_foreground` may be None, meaning "could not determine" — in that case
    the time counts, because under-reporting silently is worse than counting a
    minute the user may not have spent.
    """
    if wall_seconds <= 0:
        return 0

    # Cap first, so a sleep gap can never be credited in full.
    cap = max(poll_interval, 1.0) * SLEEP_GAP_FACTOR
    counted = min(float(wall_seconds), cap)

    if idle_seconds is not None and idle_seconds >= 0 and \
            idle_seconds >= idle_threshold_sec:
        return 0

    if require_foreground and is_foreground is False:
        return 0

    return int(counted)


def was_asleep(wall_seconds: float, poll_interval: float) -> bool:
    """True if this gap is too long to be a normal poll interval."""
    if wall_seconds <= 0:
        return False
    return wall_seconds > max(poll_interval, 1.0) * SLEEP_GAP_FACTOR
