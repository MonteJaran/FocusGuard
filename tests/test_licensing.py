"""
Entitlement (AUDIT SF-08).

Previously: config.py forced plan = "premium" on every install, every gate read
that value out of an editable JSON file, and _activate_license was a stub. There
was no path by which the product could take money.

The threat model is honest about what client-side licensing can do — see the
module docstring. These cover the parts that must be right: the default is free,
a hand-edited cache does not grant premium, and a network failure never revokes
a paying customer.
"""

import json
import time
import urllib.error

import pytest

from core import licensing
from core.config import DEFAULT_CONFIG, Config


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_a_fresh_install_is_free(config):
    """The old default was unconditional premium on every install."""
    assert licensing.is_premium(config) is False
    assert licensing.current_entitlement(config)["plan"] == licensing.FREE


def test_config_no_longer_hardcodes_a_plan():
    assert "plan" not in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["entitlement"] == {}


def test_the_premium_override_is_gone():
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "core" / "config.py")
    text = source.read_text(encoding="utf-8")
    assert 'self._data["plan"] = "premium"' not in text
    assert "Always force premium" not in text


# ── Storing and reading ───────────────────────────────────────────────────────

def test_a_stored_entitlement_grants_premium(config):
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")
    assert licensing.is_premium(config) is True


def test_entitlement_survives_a_restart(data_dir):
    licensing.store_entitlement(Config(data_dir=data_dir), licensing.PREMIUM,
                                license_key="ABC")
    assert licensing.is_premium(Config(data_dir=data_dir)) is True


def test_clearing_reverts_to_free(config):
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")
    licensing.clear_entitlement(config)
    assert licensing.is_premium(config) is False


# ── Tamper evidence ───────────────────────────────────────────────────────────

def test_hand_editing_the_plan_does_not_grant_premium(config):
    """
    The whole point: premium used to be one word in a text file. Editing the
    cached record must invalidate it rather than upgrade the user.
    """
    licensing.store_entitlement(config, licensing.FREE, license_key="")
    record = dict(config.get("entitlement"))
    record["plan"] = licensing.PREMIUM          # the obvious edit
    config.set("entitlement", record)

    assert licensing.is_premium(config) is False
    assert licensing.current_entitlement(config)["reason"] == "tampered"


def test_an_invented_entitlement_is_rejected(config):
    config.set("entitlement", {
        "plan": "premium",
        "expires_at": 0,
        "verified_at": time.time(),
        "license_key": "made-up",
        "signature": "0" * 64,
    })
    assert licensing.is_premium(config) is False


def test_an_entitlement_with_no_signature_is_rejected(config):
    config.set("entitlement", {"plan": "premium", "verified_at": time.time()})
    assert licensing.is_premium(config) is False


def test_a_malformed_entitlement_is_survived(config):
    for junk in ("premium", 42, [], None):
        config.set("entitlement", junk)
        assert licensing.is_premium(config) is False


def test_extending_the_expiry_by_hand_is_rejected(config):
    licensing.store_entitlement(config, licensing.PREMIUM,
                                expires_at=time.time() - 10, license_key="ABC")
    record = dict(config.get("entitlement"))
    record["expires_at"] = time.time() + 10_000_000
    config.set("entitlement", record)
    assert licensing.is_premium(config) is False


# ── Expiry and the offline grace period ───────────────────────────────────────

def test_an_expired_licence_is_not_premium(config):
    licensing.store_entitlement(config, licensing.PREMIUM,
                                expires_at=time.time() - 60, license_key="ABC")
    assert licensing.is_premium(config) is False
    assert licensing.current_entitlement(config)["reason"] == "expired"


def test_a_future_expiry_is_premium(config):
    licensing.store_entitlement(config, licensing.PREMIUM,
                                expires_at=time.time() + 86400, license_key="ABC")
    assert licensing.is_premium(config) is True


def test_no_expiry_means_perpetual(config):
    licensing.store_entitlement(config, licensing.PREMIUM, expires_at=0,
                                license_key="ABC")
    assert licensing.is_premium(config) is True


def test_premium_survives_being_offline_inside_the_grace_period(config):
    """Failing closed the moment the network drops punishes paying customers."""
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")
    record = dict(config.get("entitlement"))
    payload = {k: record[k] for k in ("plan", "expires_at", "verified_at",
                                      "license_key")}
    payload["verified_at"] = time.time() - (licensing.GRACE_PERIOD_DAYS - 1) * 86400
    record.update(payload)
    record["signature"] = licensing._signature(payload, licensing._cache_secret())
    config.set("entitlement", record)

    assert licensing.is_premium(config) is True


def test_premium_lapses_once_the_grace_period_runs_out(config):
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")
    record = dict(config.get("entitlement"))
    payload = {k: record[k] for k in ("plan", "expires_at", "verified_at",
                                      "license_key")}
    payload["verified_at"] = time.time() - (licensing.GRACE_PERIOD_DAYS + 1) * 86400
    record.update(payload)
    record["signature"] = licensing._signature(payload, licensing._cache_secret())
    config.set("entitlement", record)

    assert licensing.is_premium(config) is False
    assert licensing.current_entitlement(config)["reason"] == "unverified"


def test_a_freshly_verified_entitlement_is_not_stale(config):
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")
    assert licensing.current_entitlement(config)["stale"] is False


# ── Server verification ───────────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self, size=-1):
        return self._payload[:size] if size and size > 0 else self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def serve(monkeypatch, payload):
    monkeypatch.setattr(licensing.urllib.request, "urlopen",
                        lambda *_a, **_kw: FakeResponse(payload))


def fail(monkeypatch, error):
    def boom(*_a, **_kw):
        raise error

    monkeypatch.setattr(licensing.urllib.request, "urlopen", boom)


def test_a_valid_key_activates(config, monkeypatch):
    config.set("server_url", "https://example.com")
    serve(monkeypatch, {"plan": "premium", "expires_at": time.time() + 86400})

    result = licensing.activate(config, "GOOD-KEY")
    assert result["ok"] is True
    assert licensing.is_premium(config) is True


def test_a_rejected_key_does_not_activate(config, monkeypatch):
    config.set("server_url", "https://example.com")
    fail(monkeypatch, urllib.error.HTTPError(
        "https://example.com", 403, "Forbidden", {}, None))

    result = licensing.activate(config, "BAD-KEY")
    assert result["ok"] is False
    assert "not accepted" in result["message"]
    assert licensing.is_premium(config) is False


def test_an_empty_key_is_refused_without_a_request(config):
    result = licensing.activate(config, "   ")
    assert result["ok"] is False
    assert "Enter your licence key" in result["message"]


def test_activation_says_so_when_the_server_is_unreachable(config, monkeypatch):
    config.set("server_url", "https://example.com")
    fail(monkeypatch, OSError("no route to host"))

    result = licensing.activate(config, "GOOD-KEY")
    assert result["ok"] is False
    assert "internet connection" in result["message"]


def test_a_nonsense_response_does_not_activate(config, monkeypatch):
    config.set("server_url", "https://example.com")
    serve(monkeypatch, {"plan": "gold-plated"})
    assert licensing.activate(config, "KEY")["ok"] is False


def test_a_server_error_leaves_premium_intact(config, monkeypatch):
    """A 500 or a dropped connection must never revoke a paying customer."""
    config.set("server_url", "https://example.com")
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")

    fail(monkeypatch, urllib.error.HTTPError(
        "https://example.com", 500, "Server Error", {}, None))
    assert licensing.verify_with_server("ABC", "https://example.com") is None
    assert licensing.is_premium(config) is True


def test_an_oversized_response_is_refused(config, monkeypatch):
    class Huge:
        def read(self, size=-1):
            return b"x" * (licensing.MAX_RESPONSE_BYTES + 100)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(licensing.urllib.request, "urlopen",
                        lambda *_a, **_kw: Huge())
    assert licensing.verify_with_server("K", "https://example.com") is None


def test_verification_without_a_server_url_is_a_no_op():
    assert licensing.verify_with_server("KEY", "") is None


def test_verification_without_a_key_is_a_no_op():
    assert licensing.verify_with_server("", "https://example.com") is None


# ── Refresh ───────────────────────────────────────────────────────────────────

def test_a_fresh_entitlement_is_not_re_verified(config, monkeypatch):
    config.set("server_url", "https://example.com")
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")

    def should_not_run(*_a, **_kw):
        pytest.fail("re-verified an entitlement that was not stale")

    monkeypatch.setattr(licensing.urllib.request, "urlopen", should_not_run)
    assert licensing.refresh(config) is False


def test_a_revoked_licence_is_dropped_on_refresh(config, monkeypatch):
    config.set("server_url", "https://example.com")
    licensing.store_entitlement(config, licensing.PREMIUM, license_key="ABC")

    record = dict(config.get("entitlement"))
    payload = {k: record[k] for k in ("plan", "expires_at", "verified_at",
                                      "license_key")}
    payload["verified_at"] = time.time() - (licensing.REVERIFY_AFTER_HOURS + 1) * 3600
    record.update(payload)
    record["signature"] = licensing._signature(payload, licensing._cache_secret())
    config.set("entitlement", record)

    serve(monkeypatch, {"plan": "free"})
    assert licensing.refresh(config) is True
    assert licensing.is_premium(config) is False


def test_refresh_without_a_stored_key_does_nothing(config):
    assert licensing.refresh(config) is False


# ── The UI goes through the gate ──────────────────────────────────────────────

def test_the_ui_does_not_read_a_plan_config_key():
    """One gate, so there is one place to get it right."""
    from pathlib import Path

    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    for path in ui_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert 'config.get("plan")' not in text, \
            f"{path.name} reads the plan directly instead of licensing.is_premium()"


def test_activation_is_no_longer_a_stub():
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "ui" / "devices_page.py") \
        .read_text(encoding="utf-8")
    assert "coming soon" not in text.lower()
    assert "licensing.activate" in text
