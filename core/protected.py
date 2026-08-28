"""
protected.py - Processes FocusGuard must never track or terminate.

Without this list, a user can add any executable on disk as a tracked app and
give it a daily limit. Two things then go badly wrong:

  * Terminating a Windows critical process (csrss, wininit, winlogon, services,
    lsass, smss) triggers a CRITICAL_PROCESS_DIED bugcheck. The app would blue
    screen the machine.
  * Terminating Task Manager on a 5-second loop locks the user out of the one
    tool they would use to stop FocusGuard. That behaviour is also what
    antivirus heuristics score as a trojan.

The list is matched on executable name, lowercased. That is the right
granularity: calc.exe and mspaint.exe also live in System32 and are perfectly
reasonable things to limit, so a blanket "everything in System32" rule would be
wrong.
"""

import os

# Windows kernel and session infrastructure. Terminating any of these either
# bugchecks the machine or forces a logoff.
_CRITICAL = {
    "system", "registry", "memory compression", "secure system",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe",
    "fontdrvhost.exe", "dwm.exe", "sihost.exe", "logonui.exe",
    "conhost.exe", "audiodg.exe", "dllhost.exe", "wmiprvse.exe",
    "runtimebroker.exe", "taskhostw.exe", "spoolsv.exe", "wudfhost.exe",
    "ctfmon.exe", "shellexperiencehost.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
}

# The desktop shell. Killing it is survivable but wrecks the session — the
# taskbar, Start menu and every open Explorer window disappear.
_SHELL = {"explorer.exe"}

# The user's escape hatches. FocusGuard must never be able to stop someone
# from inspecting or stopping FocusGuard.
_USER_CONTROL = {
    "taskmgr.exe", "procexp.exe", "procexp64.exe", "procmon.exe",
    "perfmon.exe", "resmon.exe", "mmc.exe",
}

# Security software. Terminating antivirus is indistinguishable from malware.
_SECURITY = {
    "msmpeng.exe", "mpdefendercoreservice.exe", "nissrv.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe",
    "windefend.exe", "msseces.exe",
}

# FocusGuard itself. It runs under pythonw.exe during development and under its
# own executable once frozen; without this, tracking "Python" makes the app
# terminate itself mid-write.
_SELF = {
    "python.exe", "pythonw.exe", "focusguard.exe", "py.exe",
}

PROTECTED_PROCESS_NAMES = frozenset(
    _CRITICAL | _SHELL | _USER_CONTROL | _SECURITY | _SELF
)


def is_protected(exe_name: str = "", exe_path: str = "") -> bool:
    """
    True if this executable must never be tracked or terminated.

    Accepts either a bare executable name or a full path; a path is reduced to
    its basename so both call sites can use the same check.
    """
    for candidate in (exe_name, exe_path):
        if not candidate:
            continue
        name = os.path.basename(str(candidate).strip().replace("\\", "/")).lower()
        if name and name in PROTECTED_PROCESS_NAMES:
            return True
    return False


def protection_reason(exe_name: str = "", exe_path: str = "") -> str:
    """
    A short, user-facing explanation of why something is protected, or "" if it
    is not. Used by the add-app dialog so the refusal is not a mystery.
    """
    for candidate in (exe_name, exe_path):
        if not candidate:
            continue
        name = os.path.basename(str(candidate).strip().replace("\\", "/")).lower()
        if not name:
            continue
        if name in _CRITICAL:
            return ("This is a core Windows process. Closing it would crash "
                    "or log you out of your computer.")
        if name in _SHELL:
            return ("This is the Windows desktop. Closing it would remove your "
                    "taskbar and Start menu.")
        if name in _USER_CONTROL:
            return ("This is a system tool you need in order to manage running "
                    "programs — including FocusGuard itself.")
        if name in _SECURITY:
            return "This is security software and must keep running."
        if name in _SELF:
            return "FocusGuard runs on this, so limiting it would close FocusGuard."
    return ""
