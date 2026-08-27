"""
The staged close path (AUDIT SF-01).

The old code called psutil's kill(), i.e. TerminateProcess, with no warning and
no chance to save. These cover the policy: match the right processes, never
touch a protected one, ask politely first, and escalate only for what refuses.

Real processes are never started here — psutil is faked so the sequence can be
asserted deterministically.
"""

import sys
import types

import pytest

from core import procutil


class FakeProc:
    def __init__(self, pid, name, exe="", stubborn=False):
        self.pid = pid
        self.info = {"pid": pid, "name": name, "exe": exe}
        self._name = name
        self.stubborn = stubborn
        self.alive = True
        self.events = []

    def name(self):
        return self._name

    def terminate(self):
        self.events.append("terminate")
        self.alive = False


class FakePsutil(types.SimpleNamespace):
    """Minimal stand-in for the parts of psutil that procutil uses."""

    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass

    def __init__(self, procs):
        super().__init__()
        self._procs = procs

    def process_iter(self, _attrs=None):
        return list(self._procs)

    def Process(self, pid):  # noqa: N802 - mirrors psutil's API
        for p in self._procs:
            if p.pid == pid:
                return p
        raise self.NoSuchProcess(pid)

    def wait_procs(self, procs, timeout=None):
        gone, alive = [], []
        for p in procs:
            (alive if p.alive else gone).append(p)
        return gone, alive


@pytest.fixture
def fake(monkeypatch):
    """Install a fake psutil and record which PIDs were asked to close."""
    procs = [
        FakeProc(101, "chrome.exe", "c:/prog/chrome.exe"),
        FakeProc(102, "chrome.exe", "c:/prog/chrome.exe"),
        FakeProc(200, "csrss.exe", "c:/windows/system32/csrss.exe"),
        FakeProc(300, "taskmgr.exe", "c:/windows/system32/taskmgr.exe"),
        FakeProc(400, "code.exe", "c:/prog/code.exe", stubborn=True),
    ]
    fake_psutil = FakePsutil(procs)
    monkeypatch.setattr(procutil, "psutil", fake_psutil)
    monkeypatch.setattr(procutil, "_PSUTIL_AVAILABLE", True)

    asked = []

    def fake_request_close(pids):
        asked.extend(pids)
        for p in procs:
            if p.pid in pids and not p.stubborn:
                p.alive = False
                p.events.append("wm_close")
        return len(pids)

    monkeypatch.setattr(procutil, "request_close", fake_request_close)
    return types.SimpleNamespace(procs=procs, asked=asked,
                                 by_pid={p.pid: p for p in procs})


# ── Matching ──────────────────────────────────────────────────────────────────

def test_matches_every_process_with_the_name(fake):
    assert sorted(procutil.find_matching_pids("chrome.exe")) == [101, 102]


def test_matches_by_full_path(fake):
    assert procutil.find_matching_pids(exe_path="c:/prog/code.exe") == [400]


def test_path_matching_is_slash_insensitive(fake):
    assert procutil.find_matching_pids(exe_path=r"c:\prog\code.exe") == [400]


def test_no_match_returns_empty(fake):
    assert procutil.find_matching_pids("nothere.exe") == []


def test_empty_input_matches_nothing(fake):
    assert procutil.find_matching_pids("", "") == []


# ── Protection ────────────────────────────────────────────────────────────────

def test_protected_processes_never_match(fake):
    """Even asked for by name, a critical process must not be selected."""
    assert procutil.find_matching_pids("csrss.exe") == []
    assert procutil.find_matching_pids("taskmgr.exe") == []


def test_close_app_refuses_protected_processes(fake):
    result = procutil.close_app("csrss.exe")
    assert result["matched"] == 0
    assert result["closed"] is False
    assert fake.asked == []
    assert fake.by_pid[200].alive is True


def test_force_terminate_skips_protected_processes(fake):
    procutil.force_terminate([200, 300])
    assert fake.by_pid[200].alive is True
    assert fake.by_pid[300].alive is True


# ── The staged sequence ───────────────────────────────────────────────────────

def test_polite_close_is_tried_before_terminating(fake):
    result = procutil.close_app("chrome.exe")

    assert sorted(fake.asked) == [101, 102]
    assert result["closed"] is True
    assert result["forced"] == 0, "nothing should be terminated when WM_CLOSE works"
    for pid in (101, 102):
        assert fake.by_pid[pid].events == ["wm_close"]
        assert "terminate" not in fake.by_pid[pid].events


def test_terminate_is_the_last_resort_not_the_first(fake):
    """A process that ignores WM_CLOSE is asked first, then terminated."""
    result = procutil.close_app("code.exe", timeout=0)

    proc = fake.by_pid[400]
    assert fake.asked == [400]
    assert proc.events == ["terminate"]
    assert result["forced"] == 1
    assert result["closed"] is True


def test_summary_reports_what_happened(fake):
    result = procutil.close_app("chrome.exe")
    assert result == {"matched": 2, "asked": 2, "forced": 0, "closed": True}


def test_nothing_running_is_not_a_failure(fake):
    assert procutil.close_app("nothere.exe") == {
        "matched": 0, "asked": 0, "forced": 0, "closed": False
    }


def test_log_callback_receives_progress(fake):
    lines = []
    procutil.close_app("chrome.exe", log=lines.append)
    assert any("close" in line.lower() for line in lines)


# ── Degradation ───────────────────────────────────────────────────────────────

def test_everything_is_inert_without_psutil(monkeypatch):
    monkeypatch.setattr(procutil, "_PSUTIL_AVAILABLE", False)
    assert procutil.find_matching_pids("chrome.exe") == []
    assert procutil.force_terminate([1, 2]) == 0
    assert procutil.wait_for_exit([1], 0) == []
    assert procutil.close_app("chrome.exe")["closed"] is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fallback path")
def test_request_close_falls_back_to_sigterm_off_windows(fake, monkeypatch):
    """On non-Windows there is no WM_CLOSE; SIGTERM is the equivalent."""
    monkeypatch.undo()  # restore the real request_close
    monkeypatch.setattr(procutil, "psutil", FakePsutil(fake.procs))
    monkeypatch.setattr(procutil, "_PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(procutil, "_IS_WINDOWS", False)

    assert procutil.request_close([101]) == 1
    assert fake.by_pid[101].events == ["terminate"]
