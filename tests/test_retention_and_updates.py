"""
Data retention (ROADMAP #2, AUDIT SF-11) and the update check.

Retention was advertised as a plan feature while no pruning code existed at
all. The update check is what makes it possible to reach someone who has
already installed — without it, a security fix never reaches them.
"""

import json
from datetime import datetime, timedelta

import pytest

from core import updates
from core.config import Config
from core.database import Database
from core.monitor import Monitor


# ── Retention ─────────────────────────────────────────────────────────────────

def add_session(db, app_id, days_ago, seconds=60):
    stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
    db.end_session(db.start_session(app_id, stamp), stamp, seconds)


def test_old_sessions_are_pruned(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    add_session(db, app_id, days_ago=400)
    add_session(db, app_id, days_ago=10)

    removed = db.prune_sessions_older_than(365)

    assert removed == 1
    assert db.session_count() == 1


def test_recent_sessions_survive(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    for days in (0, 1, 30, 200):
        add_session(db, app_id, days_ago=days)

    assert db.prune_sessions_older_than(365) == 0
    assert db.session_count() == 4


def test_the_cutoff_is_exact(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    add_session(db, app_id, days_ago=31)
    add_session(db, app_id, days_ago=29)

    db.prune_sessions_older_than(30)
    assert db.session_count() == 1


def test_zero_days_keeps_everything(db):
    """0 must mean "keep forever", not "delete everything"."""
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    add_session(db, app_id, days_ago=5000)

    assert db.prune_sessions_older_than(0) == 0
    assert db.session_count() == 1


def test_negative_days_keeps_everything(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    add_session(db, app_id, days_ago=5000)

    assert db.prune_sessions_older_than(-30) == 0
    assert db.session_count() == 1


def test_pruning_does_not_touch_the_app_list(db):
    """Retention removes history, not the user's configuration."""
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    add_session(db, app_id, days_ago=400)

    db.prune_sessions_older_than(365)
    assert len(db.get_all_tracked_apps()) == 1


def test_oldest_session_date_reports_the_window(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    assert db.oldest_session_date() == ""

    add_session(db, app_id, days_ago=10)
    add_session(db, app_id, days_ago=3)
    expected = (datetime.now() - timedelta(days=10)).date().isoformat()
    assert db.oldest_session_date() == expected


def test_monitor_applies_the_configured_window(data_dir):
    db = Database(data_dir=data_dir)
    config = Config(data_dir=data_dir)
    config.set("retention_days", 30)
    try:
        app_id = db.add_tracked_app("Chrome", "chrome.exe")
        add_session(db, app_id, days_ago=90)
        add_session(db, app_id, days_ago=5)

        assert Monitor(db, config)._apply_retention() == 1
        assert db.session_count() == 1
    finally:
        db.close()


def test_monitor_honours_keep_forever(data_dir):
    db = Database(data_dir=data_dir)
    config = Config(data_dir=data_dir)
    config.set("retention_days", 0)
    try:
        app_id = db.add_tracked_app("Chrome", "chrome.exe")
        add_session(db, app_id, days_ago=9000)

        assert Monitor(db, config)._apply_retention() == 0
        assert db.session_count() == 1
    finally:
        db.close()


def test_a_garbage_retention_setting_keeps_everything(data_dir):
    """Never delete history because a setting was mistyped."""
    db = Database(data_dir=data_dir)
    config = Config(data_dir=data_dir)
    config.set("retention_days", "not a number")
    try:
        app_id = db.add_tracked_app("Chrome", "chrome.exe")
        add_session(db, app_id, days_ago=9000)

        assert Monitor(db, config)._apply_retention() == 0
        assert db.session_count() == 1
    finally:
        db.close()


# ── Version comparison ────────────────────────────────────────────────────────

@pytest.mark.parametrize("candidate,current", [
    ("1.0.1", "1.0.0"),
    ("1.1.0", "1.0.9"),
    ("2.0.0", "1.99.99"),
    ("1.10.0", "1.9.0"),      # the classic string-comparison trap
    ("1.0.0", "0.9.9"),
    ("v1.2.0", "1.1.0"),      # a leading v must not break it
])
def test_newer_versions_are_detected(candidate, current):
    assert updates.is_newer(candidate, current) is True


@pytest.mark.parametrize("candidate,current", [
    ("1.0.0", "1.0.0"),
    ("1.0.0", "1.0.1"),
    ("1.9.0", "1.10.0"),
    ("0.9.9", "1.0.0"),
    ("1.0", "1.0.0"),         # equal despite differing length
    ("1.0.0", "1.0"),
])
def test_older_or_equal_versions_are_not_offered(candidate, current):
    assert updates.is_newer(candidate, current) is False


@pytest.mark.parametrize("version,expected", [
    ("1.2.3", (1, 2, 3)),
    ("1.2", (1, 2)),
    ("10.0.0", (10, 0, 0)),
    ("1.2.3rc1", (1, 2, 3)),
    ("", (0,)),
    ("garbage", (0,)),
])
def test_version_parsing(version, expected):
    assert updates.parse_version(version) == expected


# ── Fetching the manifest ─────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, payload):
        self._payload = payload if isinstance(payload, bytes) else payload.encode()

    def read(self, size=-1):
        return self._payload[:size] if size and size > 0 else self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def serve(monkeypatch, payload):
    monkeypatch.setattr(updates.urllib.request, "urlopen",
                        lambda *_a, **_kw: FakeResponse(payload))


def test_an_available_update_is_reported(monkeypatch):
    serve(monkeypatch, json.dumps({
        "version": "9.9.9",
        "url": "https://example.com/download",
        "notes": "Fixes a crash.",
    }))
    result = updates.check(current="1.0.0")
    assert result["version"] == "9.9.9"
    assert result["url"] == "https://example.com/download"
    assert result["critical"] is False


def test_being_up_to_date_reports_nothing(monkeypatch):
    serve(monkeypatch, json.dumps({"version": "1.0.0"}))
    assert updates.check(current="1.0.0") is None


def test_a_critical_flag_is_carried_through(monkeypatch):
    serve(monkeypatch, json.dumps({"version": "2.0.0", "critical": True}))
    assert updates.check(current="1.0.0")["critical"] is True


def test_a_non_https_download_url_is_dropped(monkeypatch):
    """The manifest comes off the network; its contents are untrusted."""
    serve(monkeypatch, json.dumps({
        "version": "2.0.0",
        "url": "http://example.com/evil.exe",
    }))
    assert updates.check(current="1.0.0")["url"] == ""


def test_a_javascript_url_is_dropped(monkeypatch):
    serve(monkeypatch, json.dumps({
        "version": "2.0.0",
        "url": "javascript:alert(1)",
    }))
    assert updates.check(current="1.0.0")["url"] == ""


def test_notes_are_truncated(monkeypatch):
    serve(monkeypatch, json.dumps({"version": "2.0.0", "notes": "x" * 5000}))
    assert len(updates.check(current="1.0.0")["notes"]) <= 500


def test_an_oversized_manifest_is_refused(monkeypatch):
    serve(monkeypatch, b"x" * (updates.MAX_MANIFEST_BYTES + 100))
    assert updates.check(current="1.0.0") is None


def test_invalid_json_is_survived(monkeypatch):
    serve(monkeypatch, "{not json at all")
    assert updates.check(current="1.0.0") is None


def test_a_manifest_with_no_version_is_ignored(monkeypatch):
    serve(monkeypatch, json.dumps({"url": "https://example.com"}))
    assert updates.check(current="1.0.0") is None


def test_a_network_failure_is_not_an_error(monkeypatch):
    """The network being unavailable is the normal case for a desktop app."""
    def boom(*_a, **_kw):
        raise OSError("no route to host")

    monkeypatch.setattr(updates.urllib.request, "urlopen", boom)
    assert updates.check(current="1.0.0") is None


def test_the_background_check_never_raises(monkeypatch):
    def boom(*_a, **_kw):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(updates, "check", boom)
    called = []
    thread = updates.check_in_background(called.append)
    thread.join(timeout=5)
    assert called == []


def test_the_background_callback_receives_the_update(monkeypatch):
    serve(monkeypatch, json.dumps({"version": "9.9.9"}))
    received = []
    thread = updates.check_in_background(received.append, current="1.0.0")
    thread.join(timeout=5)
    assert received and received[0]["version"] == "9.9.9"


def test_update_checking_can_be_turned_off(config):
    """It is a network request, so it needs an opt-out and a disclosure."""
    from core.config import DEFAULT_CONFIG

    assert "check_for_updates" in DEFAULT_CONFIG
    config.set("check_for_updates", False)
    assert config.get("check_for_updates") is False


# ── The policy must match the product ─────────────────────────────────────────

def test_the_retention_control_exists_in_settings():
    """
    PRIVACY.md tells the user they can change the retention window in
    Settings. If that control is not there, the policy is a false statement —
    the same class of problem as AUDIT BL-02.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    settings = (repo_root / "ui" / "settings_page.py").read_text(encoding="utf-8")
    assert "retention_days" in settings, \
        "PRIVACY.md promises a retention setting that the UI does not offer"
    assert "Keep everything" in settings, \
        "the user must be able to opt out of automatic deletion"


def test_the_privacy_policy_names_the_real_log_file():
    from pathlib import Path

    from core import logging_setup

    repo_root = Path(__file__).resolve().parent.parent
    policy = (repo_root / "PRIVACY.md").read_text(encoding="utf-8")
    assert logging_setup.LOG_FILENAME in policy, \
        "the policy points at a log file that is no longer the one written"


def test_the_privacy_policy_discloses_the_update_check():
    """It is an outbound network request, so it has to be disclosed."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    policy = (repo_root / "PRIVACY.md").read_text(encoding="utf-8").lower()
    assert "checking for updates" in policy
    assert "ip address" in policy
