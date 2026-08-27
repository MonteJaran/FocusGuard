"""
Storage and config hardening: schema versioning (SF-07), indices (SF-11),
complete deletion (BL-06), atomic config writes (SF-12) and locking (SF-06).
"""

import json
import os
import sqlite3
import threading
from datetime import datetime

import pytest

from core.config import Config
from core.database import SCHEMA_VERSION, Database


# ── Schema versioning (SF-07) ─────────────────────────────────────────────────

def test_new_database_is_stamped_with_the_current_version(db):
    assert db.schema_version == SCHEMA_VERSION


def test_version_survives_reopen(data_dir):
    Database(data_dir=data_dir).close()
    second = Database(data_dir=data_dir)
    try:
        assert second.schema_version == SCHEMA_VERSION
    finally:
        second.close()


def test_unversioned_legacy_database_is_adopted(data_dir):
    """
    Databases created before versioning existed report user_version 0. They
    match the v1 schema, so they must be stamped, not migrated or rejected.
    """
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "focusguard.db")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE tracked_apps (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        exe_name TEXT, exe_path TEXT, root_folder TEXT,
        category TEXT DEFAULT 'Custom', enabled INTEGER DEFAULT 1,
        daily_limit_min INTEGER DEFAULT 0, weekly_limit_min INTEGER DEFAULT 0,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
    conn.execute("""CREATE TABLE usage_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, app_id INTEGER NOT NULL,
        date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT,
        duration_sec INTEGER DEFAULT 0);""")
    conn.execute("INSERT INTO tracked_apps (name, exe_name) VALUES ('Legacy', 'x.exe');")
    conn.commit()
    conn.close()

    db = Database(data_dir=data_dir)
    try:
        assert db.schema_version == SCHEMA_VERSION
        assert [a["name"] for a in db.get_all_tracked_apps()] == ["Legacy"]
    finally:
        db.close()


def test_a_newer_database_is_refused_rather_than_corrupted(data_dir):
    """Downgrading must fail loudly instead of writing an old schema over a new one."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "focusguard.db")
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5};")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="newer than this build"):
        Database(data_dir=data_dir)


# ── Indices (SF-11) ───────────────────────────────────────────────────────────

def test_lookup_indices_exist(db):
    names = {row["name"] for row in db._fetchall(
        "SELECT name FROM sqlite_master WHERE type = 'index';")}
    assert "idx_sessions_app_date" in names
    assert "idx_sessions_date" in names


def test_today_usage_query_uses_an_index(db):
    """A full table scan here runs once per app every five seconds."""
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    plan = db._fetchall(
        "EXPLAIN QUERY PLAN SELECT COALESCE(SUM(duration_sec), 0) "
        "FROM usage_sessions WHERE app_id = ? AND date = ?;",
        (app_id, "2026-01-01"),
    )
    detail = " ".join(str(row.get("detail", "")) for row in plan)
    assert "idx_sessions_app_date" in detail, detail
    assert "SCAN usage_sessions" not in detail, detail


# ── Complete deletion (BL-06) ─────────────────────────────────────────────────

def test_delete_all_data_clears_sessions_and_apps(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    now = datetime.now().isoformat()
    db.end_session(db.start_session(app_id, now), now, 900)

    db.delete_all_data()

    assert db.get_all_tracked_apps() == []
    assert db.get_all_usage_today() == []
    assert db.get_today_usage_sec(app_id) == 0


def test_history_only_deletion_keeps_the_app_list(db):
    app_id = db.add_tracked_app("Chrome", "chrome.exe")
    now = datetime.now().isoformat()
    db.end_session(db.start_session(app_id, now), now, 900)

    db.delete_all_data(include_apps=False)

    assert len(db.get_all_tracked_apps()) == 1
    assert db.get_today_usage_sec(app_id) == 0


def test_delete_removes_the_diagnostic_log(db, data_dir):
    """The log holds a plaintext record of every app opened."""
    log_path = os.path.join(data_dir, "monitor.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("[10:00:00] Poll: 'Chrome' running\n")

    assert db.delete_log_file() is True
    assert not os.path.exists(log_path)


def test_deleting_a_missing_log_is_not_an_error(db):
    assert db.delete_log_file() is False


def test_database_is_usable_after_deletion(db):
    db.add_tracked_app("Chrome", "chrome.exe")
    db.delete_all_data()
    new_id = db.add_tracked_app("Discord", "discord.exe")
    assert db.get_all_tracked_apps()[0]["name"] == "Discord"
    assert db.get_today_usage_sec(new_id) == 0


# ── Atomic config writes (SF-12) ──────────────────────────────────────────────

def test_no_temp_files_are_left_behind(data_dir):
    config = Config(data_dir=data_dir)
    for i in range(10):
        config.set("poll_interval", i)
    leftovers = [f for f in os.listdir(data_dir) if f.endswith(".tmp")]
    assert leftovers == []


def test_config_file_is_never_left_truncated(data_dir):
    """Whatever happens, the file on disk must parse."""
    config = Config(data_dir=data_dir)
    config.set("device_id", "abc123")
    with open(config.path, encoding="utf-8") as fh:
        assert json.load(fh)["device_id"] == "abc123"


def test_a_backup_is_kept(data_dir):
    config = Config(data_dir=data_dir)
    config.set("poll_interval", 30)
    config.set("poll_interval", 45)
    assert os.path.isfile(config.path + ".bak")


def test_a_damaged_config_falls_back_to_the_backup(data_dir):
    """
    A truncated write used to reset every setting to defaults, including
    device_id — which orphans the user's synced data.
    """
    config = Config(data_dir=data_dir)
    config.set("device_id", "keep-me")
    config.set("poll_interval", 30)      # ensures a .bak exists with device_id

    with open(config.path, "w", encoding="utf-8") as fh:
        fh.write('{"device_id": "keep-m')  # truncated mid-write

    recovered = Config(data_dir=data_dir)
    assert recovered.get("device_id") == "keep-me"


def test_save_reports_failure(data_dir, monkeypatch):
    config = Config(data_dir=data_dir)

    def boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr("tempfile.mkstemp", boom)
    assert config.save() is False


# ── Locking (SF-06) ───────────────────────────────────────────────────────────

def test_concurrent_writers_do_not_lose_rows(db):
    """
    The connection is opened with check_same_thread=False and written from the
    monitor, the kill watcher and the UI. Without the lock this corrupts.
    """
    errors = []

    def writer(n):
        try:
            for i in range(25):
                app_id = db.add_tracked_app(f"App{n}-{i}", f"a{n}{i}.exe")
                stamp = datetime.now().isoformat()
                db.end_session(db.start_session(app_id, stamp), stamp, 60)
        except Exception as exc:            # noqa: BLE001 - recorded, then asserted
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == [], f"concurrent writes raised: {errors}"
    assert len(db.get_all_tracked_apps()) == 100


def test_concurrent_config_writers_leave_valid_json(data_dir):
    config = Config(data_dir=data_dir)
    errors = []

    def writer(n):
        try:
            for i in range(20):
                config.set(f"key_{n}", i)
        except Exception as exc:            # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == []
    with open(config.path, encoding="utf-8") as fh:
        data = json.load(fh)          # must parse
    assert all(f"key_{n}" in data for n in range(4))
