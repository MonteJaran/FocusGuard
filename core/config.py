"""
config.py - JSON configuration for FocusGuard.
"""

import os
import json

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FocusGuard")
_CONFIG_PATH = os.path.join(_DATA_DIR, "config.json")

DEFAULT_CONFIG: dict = {
    "poll_interval": 60,           # seconds
    "start_minimized": False,
    "notifications_enabled": True,
    "notification_sound": False,
    "warn_at_percent": 80,
    "auto_kill_over_limit": False,  # force-close apps that exceed daily limit
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
        self._load()

    @property
    def path(self) -> str:
        return self._path

    @property
    def data_dir(self) -> str:
        return self._dir

    def _load(self) -> None:
        if os.path.isfile(self._path):
            try:
                with open(self._path, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                # Merge with defaults so new keys are always present
                self._data = {**DEFAULT_CONFIG, **loaded}
                # Always keep server_url up to date with the latest deployed URL
                if not self._data.get("server_url"):
                    self._data["server_url"] = DEFAULT_CONFIG["server_url"]
            except (json.JSONDecodeError, OSError):
                self._data = dict(DEFAULT_CONFIG)
        else:
            self._data = dict(DEFAULT_CONFIG)
        # Always force premium so Pro features are available for testing
        self._data["plan"] = "premium"
        self.save()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except OSError:
            pass
