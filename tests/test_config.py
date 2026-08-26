"""Configuration: defaults, persistence, and recovery from a damaged file."""

import json
import os

from core.config import DEFAULT_CONFIG, Config


def test_defaults_are_applied_on_first_run(config):
    assert config.get("poll_interval") == 60
    assert config.get("notifications_enabled") is True
    assert config.get("auto_kill_over_limit") is False
    assert config.get("warn_at_percent") == 80


def test_get_returns_fallback_for_unknown_key(config):
    assert config.get("no_such_key") is None
    assert config.get("no_such_key", "fallback") == "fallback"


def test_set_persists_to_disk(data_dir):
    first = Config(data_dir=data_dir)
    first.set("poll_interval", 15)
    first.set("warn_at_percent", 50)

    second = Config(data_dir=data_dir)
    assert second.get("poll_interval") == 15
    assert second.get("warn_at_percent") == 50


def test_config_file_is_created(config):
    assert os.path.isfile(config.path)
    with open(config.path, encoding="utf-8") as fh:
        assert json.load(fh)["poll_interval"] == 60


def test_new_default_keys_are_merged_into_an_old_file(data_dir):
    """An install from an older version must gain keys added since."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"poll_interval": 5}, fh)

    config = Config(data_dir=data_dir)
    assert config.get("poll_interval") == 5                       # kept
    assert config.get("warn_at_percent") == 80                    # filled in
    assert config.get("consent_version") == 0                     # filled in


def test_corrupt_file_falls_back_to_defaults(data_dir):
    """A truncated write must not brick the app (AUDIT SF-12)."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"poll_interval": 30, "start_min')   # truncated mid-write

    config = Config(data_dir=data_dir)
    assert config.get("poll_interval") == DEFAULT_CONFIG["poll_interval"]


def test_empty_server_url_is_repopulated(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"server_url": ""}, fh)

    assert Config(data_dir=data_dir).get("server_url") == DEFAULT_CONFIG["server_url"]


def test_consent_keys_exist_in_defaults():
    """The consent gate depends on these being present from a clean install."""
    for key in ("consent_version", "consent_accepted", "consent_at"):
        assert key in DEFAULT_CONFIG


def test_consent_defaults_to_not_given():
    assert DEFAULT_CONFIG["consent_version"] == 0
    assert DEFAULT_CONFIG["consent_accepted"] is False


def test_values_of_every_type_round_trip(data_dir):
    first = Config(data_dir=data_dir)
    first.set("a_bool", True)
    first.set("an_int", 42)
    first.set("a_list", [{"id": "x", "name": "PC"}])
    first.set("a_dict", {"1": "abc"})

    second = Config(data_dir=data_dir)
    assert second.get("a_bool") is True
    assert second.get("an_int") == 42
    assert second.get("a_list") == [{"id": "x", "name": "PC"}]
    assert second.get("a_dict") == {"1": "abc"}
