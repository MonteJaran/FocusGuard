"""
config.py - JSON configuration for FocusGuard.
"""

import json
import os
import tempfile
import threading

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FocusGuard")
_CONFIG_PATH = os.path.join(_DATA_DIR, "config.json")

DEFAULT_CONFIG: dict = {
    "poll_interval": 60,           # seconds
    "start_minimized": False,
    "notifications_enabled": True,
    "notification_sound": False,
    "warn_at_percent": 80,
    "auto_kill_over_limit": False,  # close apps that exceed their daily limit
    # Warning period between hitting the limit and the app being closed, so
    # the user has time to save. Floored at MIN_GRACE_SECONDS in monitor.py.
    "close_grace_seconds": 60,
    "first_run": True,
    # Privacy consent (see core/consent.py). 0 = never accepted; the app shows
    # the consent gate and records nothing until this matches CONSENT_VERSION.
    "consent_version": 0,
    "consent_accepted": False,
    "consent_at": "",
    # Device & plan
    "device_id": "",               # 24-char server-assigned ID
    "server_url": "https://api-tk3y3h4s3q-uc.a.run.app",  # Firebase Cloud Functions
    "plan": "premium",             # "freemium" or "premium"
    "linked_devices": [],          # [{id, name, last_seen}, ...]
    "server_app_ids": {},          # {local_db_id: server_id} mapping
}


class Config:
    def __init__(self, data_dir: str = "") -> None:
        # data_dir is injectable so tests can run against a temp directory
        # instead of the real %LOCALAPPDATA%.
        self._dir = data_dir or _DATA_DIR
        os.makedirs(self._dir, exist_ok=True)
        self._path = (_CONFIG_PATH if not data_dir
                      else os.path.join(self._dir, "config.json"))
        self._data: dict = {}
        # save() is reachable from the monitor thread, the kill watcher and the
        # UI; without this two threads can interleave and write a mangled file.
        self._lock = threading.RLock()
        self._load()

    @property
    def path(self) -> str:
        return self._path

    @property
    def data_dir(self) -> str:
        return self._dir

    def _load(self) -> None:
        loaded = self._read_file(self._path)
        if loaded is None:
            # The live file is missing or damaged — try the backup written by
            # the previous successful save before falling back to defaults, so
            # a truncated write does not silently reset every setting
            # (including device_id, which orphans the user's synced data).
            loaded = self._read_file(self._path + ".bak")

        if loaded is None:
            self._data = dict(DEFAULT_CONFIG)
        else:
            # Merge with defaults so new keys are always present
            self._data = {**DEFAULT_CONFIG, **loaded}
            # Always keep server_url up to date with the latest deployed URL
            if not self._data.get("server_url"):
                self._data["server_url"] = DEFAULT_CONFIG["server_url"]
        # Always force premium so Pro features are available for testing
        self._data["plan"] = "premium"
        self.save()

    @staticmethod
    def _read_file(path: str):
        """Parse a config file, or None if it is missing or unreadable."""
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = value
            self.save()

    def save(self) -> bool:
        """
        Write the config atomically.

        json.dump straight over the live file means a crash or power loss
        mid-write leaves a truncated file, and every setting resets to defaults
        on next launch. Writing to a temp file in the same directory and then
        os.replace()-ing it over the target is atomic on both Windows and POSIX:
        the config is either the old one or the new one, never half of each.

        Returns False if the write failed, so a caller can tell.
        """
        with self._lock:
            payload = json.dumps(self._data, indent=2)
            tmp_path = ""
            try:
                # Same directory, so os.replace() stays on one filesystem.
                fd, tmp_path = tempfile.mkstemp(
                    dir=self._dir, prefix=".config-", suffix=".tmp"
                )
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())

                # Keep the last good copy so _load() has something to fall
                # back to if this file is ever damaged.
                if os.path.isfile(self._path):
                    try:
                        os.replace(self._path, self._path + ".bak")
                    except OSError:
                        pass

                os.replace(tmp_path, self._path)
                return True
            except OSError:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                return False
