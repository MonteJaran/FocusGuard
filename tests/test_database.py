"""Storage layer: app records, session lifecycle, and usage aggregation."""

from datetime import date, datetime, timedelta

import pytest

from core.database import Database


# ── Tracked apps ──────────────────────────────────────────────────────────────

def test_starts_empty(db):
    assert db.get_all_tracked_apps() == []


def test_add_and_read_back(db):
    app_id = db.add_tracked_app("Discord", "discord.exe", r"C:\d\discord.exe",
                                r"C:\d", "Communication")
    apps = db.get_all_tracked_apps()
    assert len(apps) == 1
    assert apps[0]["id"] == app_id
    assert apps[0]["name"] == "Discord"
    assert apps[0]["category"] == "Communication"
    assert apps[0]["enabled"] == 1
    assert apps[0]["daily_limit_min"] == 0


def test_apps_are_sorted_by_name(db):
    for name in ("Zoom", "Amp", "Mail"):
        db.add_tracked_app(name, f"{name.lower()}.exe")
    assert [a["name"] for a in db.get_all_tracked_apps()] == ["Amp", "Mail", "Zoom"]


def test_lookup_by_exe_name_is_case_insensitive(db):
    db.add_tracked_app("Chrome", "chrome.exe")
    assert db.get_app_by_exe_name("CHROME.EXE")["name"] == "Chrome"
    assert db.get_app_by_exe_name("Chrome.Exe")["name"] == "Chrome"


def test_lookup_misses_return_none(db):
    assert db.get_app_by_exe_name("nothing.exe") is None


def test_set_enabled_and_limits(db):
    app_id = db.add_tracked_app("Slack", "slack.exe")
    db.set_app_enabled(app_id, False)
    db.set_app_limits(app_id, 45, 300)
    app = db.get_all_tracked_apps()[0]
    assert app["enabled"] == 0
    assert app["daily_limit_min"] == 45
    assert app["weekly_limit_min"] == 300


def test_update_without_category_preserves_it(db):
    app_id = db.add_tracked_app("Figma", "figma.exe", category="Creative")
    db.update_tracked_app(app_id, "Figma Desktop", "figma.exe", "", "")
    app = db.get_all_tracked_apps()[0]
    assert app["name"] == "Figma Desktop"
    assert app["category"] == "Creative"


def test_remove_app(db):
    app_id = db.add_tracked_app("Steam", "steam.exe")
    db.remove_tracked_app(app_id)
    assert db.get_all_tracked_apps() == []


def test_removing_app_cascades_to_its_sessions(db):
    app_id = db.add_tracked_app("Steam", "steam.exe")
    sid = db.start_session(app_id, datetime.now().isoformat())
    db.end_session(sid, datetime.now().isoformat(), 600)
    db.remove_tracked_app(app_id)
    assert db.get_all_usage_today() == []


# ── Sessions ──────────────────────────────────────────────────────────────────

def test_session_lifecycle(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    start = datetime.now()
    sid = db.start_session(app_id, start.isoformat())
    assert db.get_today_usage_sec(app_id) == 0

    db.end_session(sid, (start + timedelta(minutes=30)).isoformat(), 1800)
    assert db.get_today_usage_sec(app_id) == 1800


def test_mid_session_checkpoint_is_visible(db):
    """Duration is saved mid-flight so a crash doesn't lose the session."""
    app_id = db.add_tracked_app("Code", "code.exe")
    sid = db.start_session(app_id, datetime.now().isoformat())
    db.update_session_duration(sid, 420)
    assert db.get_today_usage_sec(app_id) == 420


def test_multiple_sessions_sum(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    now = datetime.now()
    for seconds in (600, 900, 300):
        sid = db.start_session(app_id, now.isoformat())
        db.end_session(sid, now.isoformat(), seconds)
    assert db.get_today_usage_sec(app_id) == 1800


def test_usage_is_scoped_per_app(db):
    a = db.add_tracked_app("A", "a.exe")
    b = db.add_tracked_app("B", "b.exe")
    now = datetime.now().isoformat()
    db.end_session(db.start_session(a, now), now, 100)
    db.end_session(db.start_session(b, now), now, 250)
    assert db.get_today_usage_sec(a) == 100
    assert db.get_today_usage_sec(b) == 250


def test_week_usage_includes_last_seven_days_only(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    for days_ago, seconds in ((0, 100), (3, 200), (6, 300), (7, 999), (30, 999)):
        stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
        db.end_session(db.start_session(app_id, stamp), stamp, seconds)

    assert db.get_today_usage_sec(app_id) == 100
    assert db.get_week_usage_sec(app_id) == 600     # 8-day-old rows excluded


def test_usage_history_groups_by_date(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    for days_ago in (0, 0, 2):
        stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
        db.end_session(db.start_session(app_id, stamp), stamp, 60)

    history = db.get_usage_history(app_id, days=30)
    assert len(history) == 2
    assert history[-1]["date"] == date.today().isoformat()
    assert history[-1]["total_sec"] == 120
    assert [h["date"] for h in history] == sorted(h["date"] for h in history)


def test_usage_history_respects_the_cutoff(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    old = (datetime.now() - timedelta(days=40)).isoformat()
    db.end_session(db.start_session(app_id, old), old, 60)
    assert db.get_usage_history(app_id, days=30) == []


# ── Aggregation ───────────────────────────────────────────────────────────────

def test_all_usage_today_is_sorted_by_duration(db):
    small = db.add_tracked_app("Small", "s.exe")
    large = db.add_tracked_app("Large", "l.exe")
    now = datetime.now().isoformat()
    db.end_session(db.start_session(small, now), now, 60)
    db.end_session(db.start_session(large, now), now, 6000)

    rows = db.get_all_usage_today()
    assert [r["name"] for r in rows] == ["Large", "Small"]
    assert rows[0]["duration_sec"] == 6000


def test_category_usage_sums_across_apps(db):
    a = db.add_tracked_app("Chrome", "chrome.exe", category="Browser")
    b = db.add_tracked_app("Firefox", "firefox.exe", category="Browser")
    c = db.add_tracked_app("Code", "code.exe", category="Development")
    now = datetime.now().isoformat()
    for app_id, seconds in ((a, 100), (b, 200), (c, 50)):
        db.end_session(db.start_session(app_id, now), now, seconds)

    by_cat = {r["category"]: r["total_sec"] for r in db.get_category_usage_week()}
    assert by_cat == {"Browser": 300, "Development": 50}


def test_peak_hours_buckets_by_hour_of_day(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    today = date.today().isoformat()
    for hour, seconds in ((9, 600), (9, 300), (14, 1200)):
        stamp = f"{today}T{hour:02d}:15:00"
        db.end_session(db.start_session(app_id, stamp), stamp, seconds)

    by_hour = {r["hour"]: r["total_sec"] for r in db.get_peak_hours(days=7)}
    assert by_hour[9] == 900
    assert by_hour[14] == 1200


def test_aggregations_are_empty_with_no_data(db):
    assert db.get_all_usage_today() == []
    assert db.get_category_usage_week() == []
    assert db.get_all_apps_week_usage() == []


# ── Deletion ──────────────────────────────────────────────────────────────────

def test_delete_all_data_clears_sessions(db):
    app_id = db.add_tracked_app("Code", "code.exe")
    now = datetime.now().isoformat()
    db.end_session(db.start_session(app_id, now), now, 500)

    db.delete_all_data()
    assert db.get_today_usage_sec(app_id) == 0


@pytest.mark.xfail(
    reason="AUDIT BL-06: delete_all_data() clears sessions but leaves the "
           "tracked-app list, so the UI's 'All usage data has been deleted' "
           "is not true yet.",
    strict=True,
)
def test_delete_all_data_also_clears_tracked_apps(db):
    db.add_tracked_app("Code", "code.exe")
    db.delete_all_data()
    assert db.get_all_tracked_apps() == []


# ── Persistence & safety ──────────────────────────────────────────────────────

def test_data_survives_reopen(data_dir):
    first = Database(data_dir=data_dir)
    app_id = first.add_tracked_app("Code", "code.exe")
    now = datetime.now().isoformat()
    first.end_session(first.start_session(app_id, now), now, 750)
    first.close()

    second = Database(data_dir=data_dir)
    try:
        assert second.get_today_usage_sec(app_id) == 750
        assert len(second.get_all_tracked_apps()) == 1
    finally:
        second.close()


def test_app_names_with_quotes_are_not_injectable(db):
    """Every query is parameterised — a name full of SQL must round-trip."""
    nasty = "'; DROP TABLE tracked_apps; --"
    app_id = db.add_tracked_app(nasty, "x.exe")
    assert db.get_all_tracked_apps()[0]["name"] == nasty
    # The table still exists and still works.
    assert db.get_today_usage_sec(app_id) == 0


def test_close_is_idempotent(data_dir):
    database = Database(data_dir=data_dir)
    database.close()
    database.close()
