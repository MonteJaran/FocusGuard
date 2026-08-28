"""
The protected-process denylist (AUDIT SF-02).

Terminating a Windows critical process bugchecks the machine; terminating Task
Manager locks the user out of stopping FocusGuard. Neither must ever be
possible, so these are enforced rather than documented.
"""

import pytest

from core.apps_list import DEFAULT_APPS
from core.protected import PROTECTED_PROCESS_NAMES, is_protected, protection_reason

# Terminating any of these bugchecks Windows or forces a logoff.
CRITICAL = [
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "smss.exe", "svchost.exe",
]

# The user must always be able to inspect and stop FocusGuard.
ESCAPE_HATCHES = ["taskmgr.exe", "procexp.exe", "perfmon.exe"]

# FocusGuard runs on these; closing them closes FocusGuard mid-write.
SELF = ["python.exe", "pythonw.exe", "focusguard.exe"]

# Ordinary apps a user is entitled to limit. These must NOT be protected.
LIMITABLE = [
    "chrome.exe", "discord.exe", "steam.exe", "code.exe", "spotify.exe",
    "calc.exe", "mspaint.exe", "notepad.exe", "firefox.exe",
]


@pytest.mark.parametrize("name", CRITICAL + ESCAPE_HATCHES + SELF)
def test_protected_names_are_blocked(name):
    assert is_protected(name) is True


@pytest.mark.parametrize("name", LIMITABLE)
def test_ordinary_apps_are_not_blocked(name):
    assert is_protected(name) is False, f"{name} is a legitimate app to limit"


def test_explorer_is_protected():
    """Killing the shell removes the taskbar and Start menu."""
    assert is_protected("explorer.exe") is True


def test_defender_is_protected():
    assert is_protected("MsMpEng.exe") is True


def test_matching_is_case_insensitive():
    assert is_protected("CSRSS.EXE") is True
    assert is_protected("Taskmgr.Exe") is True


def test_full_paths_are_reduced_to_the_executable_name():
    assert is_protected(exe_path=r"C:\Windows\System32\csrss.exe") is True
    assert is_protected(exe_path="C:/Windows/System32/Taskmgr.exe") is True
    assert is_protected(exe_path=r"C:\Program Files\Steam\steam.exe") is False


def test_either_field_alone_is_enough():
    assert is_protected(exe_name="lsass.exe", exe_path="") is True
    assert is_protected(exe_name="", exe_path=r"C:\Windows\System32\lsass.exe") is True


def test_empty_input_is_not_protected():
    assert is_protected() is False
    assert is_protected("", "") is False
    assert is_protected(None, None) is False


def test_surrounding_whitespace_does_not_bypass_the_check():
    assert is_protected("  csrss.exe  ") is True


def test_every_protected_name_is_lowercase():
    """Matching lowercases the input, so an uppercase entry could never hit."""
    for name in PROTECTED_PROCESS_NAMES:
        assert name == name.lower(), f"{name!r} would never match"


def test_protection_reason_is_given_for_protected_processes():
    for name in CRITICAL + ESCAPE_HATCHES + SELF:
        assert protection_reason(name), f"no explanation for {name}"


def test_protection_reason_is_empty_for_ordinary_apps():
    assert protection_reason("chrome.exe") == ""


def test_reasons_are_written_for_users_not_developers():
    reason = protection_reason("csrss.exe")
    assert "crash" in reason.lower() or "log you out" in reason.lower()
    assert "bugcheck" not in reason.lower()


# ── The preloaded catalogue ───────────────────────────────────────────────────

def test_catalogue_offers_no_protected_apps():
    """
    Task Manager and PowerShell used to ship as ready-made kill targets.
    Nothing protected may be offered for tracking.
    """
    offending = [
        app["name"] for app in DEFAULT_APPS
        if is_protected(app.get("exe_name", ""))
    ]
    assert offending == [], f"protected apps in the catalogue: {offending}"


def test_task_manager_is_not_in_the_catalogue():
    names = {app["name"].lower() for app in DEFAULT_APPS}
    assert "task manager" not in names


def test_catalogue_still_has_useful_entries():
    """Guard against the removal above being over-broad."""
    assert len(DEFAULT_APPS) > 90
    names = {app["name"] for app in DEFAULT_APPS}
    assert "Google Chrome" in names
