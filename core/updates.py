"""
updates.py - Telling the user when a newer version exists.

Without this there is no way to reach someone who has already installed. Ship a
security fix and every existing install stays on the broken version forever.

Deliberately minimal. It fetches one small static JSON file and compares
versions; it does not download or install anything, because an app that can
silently replace its own executable is a far larger security surface than this
project can currently justify. The user is told, and clicks through to the
download themselves.

The manifest is a static file, so it can be hosted free on GitHub Pages,
Cloudflare Pages, or any static host. No backend required:

    {
      "version": "1.1.0",
      "url": "https://focusguard.app/download",
      "notes": "Fixes a crash when...",
      "critical": false
    }

`critical` marks a security fix, so the UI can say so plainly rather than
looking like every other "an update is available" nag.
"""

import json
import threading
import urllib.error
import urllib.request

from core.logging_setup import get_logger
from core.version import __version__

log = get_logger("updates")

# Where the manifest lives. Static file, no server needed.
UPDATE_MANIFEST_URL = "https://focusguard.app/version.json"

# Short: this must never delay startup or hold the app open on shutdown.
REQUEST_TIMEOUT = 8

# The manifest is tiny. Anything larger is wrong, and refusing to read it
# stops a hostile or misconfigured host feeding the parser something huge.
MAX_MANIFEST_BYTES = 8 * 1024


def parse_version(version: str) -> tuple:
    """
    A version string as a comparable tuple of integers.

    Deliberately not a string comparison: "1.10.0" < "1.9.0" is True as text
    and false in fact, which is the classic way this goes wrong. Non-numeric
    trailing parts (rc1, beta) are dropped rather than guessed at.
    """
    parts = []
    for chunk in str(version).strip().lstrip("vV").split("."):
        digits = ""
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        if digits == "":
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    """True if `candidate` is a strictly newer version than `current`."""
    left, right = parse_version(candidate), parse_version(current)
    # Pad so (1, 1) and (1, 1, 0) compare equal rather than by length.
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return left > right


def fetch_manifest(url: str = UPDATE_MANIFEST_URL, timeout: int = REQUEST_TIMEOUT):
    """
    Fetch and parse the update manifest, or None if anything goes wrong.

    Never raises: a failed update check is not worth an error dialog, and the
    network being unavailable is the normal case for a desktop app.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"FocusGuard/{__version__}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_MANIFEST_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.debug("Update check could not reach %s: %s", url, e)
        return None

    if len(raw) > MAX_MANIFEST_BYTES:
        log.warning("Update manifest at %s is larger than expected; ignoring.", url)
        return None

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        log.warning("Update manifest is not valid JSON: %s", e)
        return None

    if not isinstance(data, dict) or not data.get("version"):
        log.warning("Update manifest has no version field; ignoring.")
        return None
    return data


def check(url: str = UPDATE_MANIFEST_URL, current: str = __version__):
    """
    Check for a newer version.

    Returns a dict describing the update, or None if there is none or the check
    failed. The caller cannot tell those two apart on purpose — both mean
    "carry on, say nothing".
    """
    manifest = fetch_manifest(url)
    if manifest is None:
        return None

    latest = str(manifest["version"]).strip()
    if not is_newer(latest, current):
        log.debug("Up to date (running %s, latest %s).", current, latest)
        return None

    download_url = str(manifest.get("url") or "").strip()
    # Only ever hand an https link to the browser. A manifest is fetched from
    # the network, so treat its contents as untrusted input.
    if not download_url.lower().startswith("https://"):
        log.warning("Update manifest download URL is not https; ignoring it.")
        download_url = ""

    log.info("Update available: %s (running %s).", latest, current)
    return {
        "version": latest,
        "url": download_url,
        "notes": str(manifest.get("notes") or "").strip()[:500],
        "critical": bool(manifest.get("critical", False)),
    }


def check_in_background(callback, url: str = UPDATE_MANIFEST_URL,
                        current: str = __version__) -> threading.Thread:
    """
    Run check() off the main thread and hand the result to `callback`.

    The callback fires only when there IS an update, and runs on the worker
    thread — a Tk caller must marshal back with root.after().
    """
    def _run():
        try:
            result = check(url, current)
        except Exception as e:
            log.error("Update check failed unexpectedly: %s", e)
            return
        if result and callback:
            try:
                callback(result)
            except Exception as e:
                log.error("Update callback failed: %s", e)

    thread = threading.Thread(target=_run, daemon=True,
                              name="FocusGuard-UpdateCheck")
    thread.start()
    return thread
