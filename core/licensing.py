"""
licensing.py - Who is entitled to what.

Replaces the previous arrangement, which was not an arrangement at all:
`config.py` forced `plan = "premium"` on every install, every gate read that
value straight out of an editable JSON file, and `_activate_license` was a stub
that showed "coming soon". There was no path by which the product could take
money (AUDIT SF-08).

## What this can and cannot do

Be honest about the threat model. This is desktop software: the machine belongs
to the user, so a determined person can always patch the binary. Client-side
licensing is **deterrence, not security**, and pretending otherwise leads to
building elaborate schemes that cost real engineering and stop nobody.

So the design splits the problem:

  * The **server is the authority**. Anything that actually costs money to
    provide -- cross-device sync, hosted storage -- must be gated server-side
    at the point of use, where the client cannot argue with it.
  * The **client caches** the server's answer so the app works offline, and the
    cache is *tamper-evident* rather than tamper-proof: editing config.json by
    hand invalidates it and drops you back to free. That stops casual editing,
    which is the realistic case, and does not pretend to stop more.

## Offline behaviour

Failing closed the moment the network drops would punish paying customers for
being on a train. A verified entitlement therefore stays valid for
GRACE_PERIOD_DAYS after its last successful check, and only then degrades to
free. Re-verification is attempted well before that.
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid

from core.logging_setup import get_logger

log = get_logger("licensing")

FREE = "free"
PREMIUM = "premium"

# How long a verified entitlement survives without a successful re-check.
GRACE_PERIOD_DAYS = 14

# Re-verify once a day when online; the grace period covers everything else.
REVERIFY_AFTER_HOURS = 24

REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 8 * 1024

_DAY = 86400


def _machine_binding() -> str:
    """
    A stable per-machine value used to bind the cached entitlement.

    Deliberately weak and deliberately local: it exists so that copying
    config.json to another PC does not carry a licence with it, not to
    fingerprint anyone. It never leaves the machine and is not sent anywhere.
    """
    return f"{uuid.getnode():x}"


def _signature(payload: dict, secret: str) -> str:
    """Tamper-evidence over the cached entitlement."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def _cache_secret() -> str:
    # Machine-bound rather than a constant baked into the binary: a shared
    # constant would be extracted once and posted publicly, and this at least
    # makes a stolen config.json useless elsewhere.
    return f"focusguard-entitlement-{_machine_binding()}"


# ── Reading the current entitlement ───────────────────────────────────────────

def current_entitlement(config) -> dict:
    """
    What this install is entitled to right now.

    Returns {"plan", "expires_at", "verified_at", "stale", "reason"}. Always
    returns something usable — an unreadable or tampered cache is simply free.
    """
    free = {"plan": FREE, "expires_at": 0, "verified_at": 0,
            "stale": False, "reason": ""}

    raw = config.get("entitlement") or {}
    if not isinstance(raw, dict) or not raw.get("signature"):
        return free

    payload = {k: raw.get(k) for k in ("plan", "expires_at", "verified_at",
                                       "license_key")}
    expected = _signature(payload, _cache_secret())
    if not hmac.compare_digest(expected, str(raw.get("signature", ""))):
        log.warning("Stored entitlement failed its integrity check; "
                    "treating this install as free.")
        return {**free, "reason": "tampered"}

    now = time.time()

    expires_at = float(payload.get("expires_at") or 0)
    if expires_at and now > expires_at:
        return {**free, "reason": "expired"}

    verified_at = float(payload.get("verified_at") or 0)
    if now - verified_at > GRACE_PERIOD_DAYS * _DAY:
        log.info("Entitlement has not been verified for %d days; "
                 "falling back to free.", GRACE_PERIOD_DAYS)
        return {**free, "reason": "unverified"}

    return {
        "plan": payload.get("plan") or FREE,
        "expires_at": expires_at,
        "verified_at": verified_at,
        "stale": (now - verified_at) > REVERIFY_AFTER_HOURS * 3600,
        "reason": "",
    }


def is_premium(config) -> bool:
    """
    The single gate. Every tier check in the UI goes through this rather than
    reading a config key, so there is exactly one place to get it right.
    """
    return current_entitlement(config)["plan"] == PREMIUM


def store_entitlement(config, plan: str, expires_at: float = 0,
                      license_key: str = "") -> dict:
    """Cache a verified entitlement, signed so hand-editing invalidates it."""
    payload = {
        "plan": plan,
        "expires_at": float(expires_at or 0),
        "verified_at": time.time(),
        "license_key": license_key,
    }
    record = dict(payload)
    record["signature"] = _signature(payload, _cache_secret())
    config.set("entitlement", record)
    return record


def clear_entitlement(config) -> None:
    config.set("entitlement", {})


# ── Talking to the server ─────────────────────────────────────────────────────

def verify_with_server(license_key: str, server_url: str,
                       device_id: str = "", timeout: int = REQUEST_TIMEOUT):
    """
    Ask the server what this licence is worth.

    Returns the parsed response, or None if the server could not be reached or
    said something unusable. None means "do not change anything" — a network
    failure must never revoke a paying customer's access; that is what the
    grace period is for.

    Expected response:
        {"plan": "premium", "expires_at": 1790000000}
    """
    base = (server_url or "").rstrip("/")
    if not base or not license_key:
        return None

    body = json.dumps({"k": license_key, "d": device_id}).encode()
    request = urllib.request.Request(
        f"{base}/license/verify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (402, 403, 404, 410):
            # The server actively says this licence is not valid. That is an
            # answer, not a failure, so it is worth acting on.
            log.info("Server rejected licence (HTTP %s).", e.code)
            return {"plan": FREE, "expires_at": 0, "rejected": True}
        log.warning("Licence verification failed: HTTP %s", e.code)
        return None
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.debug("Could not reach the licence server: %s", e)
        return None

    if len(raw) > MAX_RESPONSE_BYTES:
        log.warning("Licence response was larger than expected; ignoring.")
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        log.warning("Licence response was not valid JSON: %s", e)
        return None

    if not isinstance(data, dict) or data.get("plan") not in (FREE, PREMIUM):
        log.warning("Licence response had no usable plan; ignoring.")
        return None
    return data


def activate(config, license_key: str) -> dict:
    """
    Activate a licence key.

    Returns {"ok": bool, "message": str} — the message is shown to the user, so
    it says what happened and what to do about it.
    """
    key = (license_key or "").strip()
    if not key:
        return {"ok": False, "message": "Enter your licence key first."}

    server_url = config.get("server_url") or ""
    if not server_url:
        return {"ok": False,
                "message": "No licence server is configured, so keys cannot "
                           "be checked yet."}

    result = verify_with_server(key, server_url, config.get("device_id") or "")

    if result is None:
        return {"ok": False,
                "message": "Could not reach the licence server. Check your "
                           "internet connection and try again."}

    if result.get("rejected") or result.get("plan") != PREMIUM:
        return {"ok": False,
                "message": "That licence key was not accepted. Check it for "
                           "typos, or contact support if it should be valid."}

    store_entitlement(config, PREMIUM, result.get("expires_at", 0), key)
    log.info("Licence activated.")
    return {"ok": True, "message": "Premium activated. Thank you."}


def refresh(config) -> bool:
    """
    Re-check a stored licence against the server, if it is due.

    Returns True if anything changed. Safe to call on a background thread; a
    failure leaves the cached entitlement alone.
    """
    entitlement = current_entitlement(config)
    stored = config.get("entitlement") or {}
    key = stored.get("license_key") or ""

    if not key or not entitlement.get("stale"):
        return False

    result = verify_with_server(key, config.get("server_url") or "",
                                config.get("device_id") or "")
    if result is None:
        return False

    if result.get("plan") == PREMIUM:
        store_entitlement(config, PREMIUM, result.get("expires_at", 0), key)
    else:
        log.info("Licence is no longer valid; reverting to free.")
        clear_entitlement(config)
    return True
