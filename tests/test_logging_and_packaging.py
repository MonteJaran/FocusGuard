"""
Logging (SF-10, SF-13), the version single-source and dependency hygiene
(ST-07, BL-05).
"""

import logging
import os
import re
from pathlib import Path

import pytest

from core import logging_setup
from core.database import Database
from core.version import APP_NAME, __version__

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    """
    Read the version out of pyproject.toml without a TOML parser: tomllib is
    stdlib only from 3.11, and 3.10 is the declared floor.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no version"
    return match.group(1)


def _pyproject_dependencies() -> set:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text,
                      re.MULTILINE | re.DOTALL)
    assert block, "pyproject.toml has no dependencies list"
    return {
        name.split(">")[0].split("=")[0].strip().lower()
        for name in re.findall(r'"([^"]+)"', block.group(1))
    }


@pytest.fixture
def fresh_logging(data_dir):
    logging_setup.configure(data_dir, level=logging.DEBUG, force=True)
    yield data_dir
    for handler in list(logging.getLogger("focusguard").handlers):
        handler.close()


# ── Logging ───────────────────────────────────────────────────────────────────

def test_log_file_is_written(fresh_logging):
    logging_setup.get_logger("test").warning("hello")
    path = os.path.join(fresh_logging, logging_setup.LOG_FILENAME)
    assert os.path.isfile(path)
    assert "hello" in open(path, encoding="utf-8").read()


def test_entries_carry_a_date(fresh_logging):
    """
    The old format was %H:%M:%S with no date, which made the log useless for
    anything spanning more than a day.
    """
    logging_setup.get_logger("test").warning("dated")
    text = open(os.path.join(fresh_logging, logging_setup.LOG_FILENAME),
                encoding="utf-8").read()
    assert text[:4].isdigit(), f"no year at the start of: {text[:40]!r}"
    assert text[4] == "-" and text[7] == "-"


def test_entries_carry_a_level_and_source(fresh_logging):
    logging_setup.get_logger("monitor").error("boom")
    text = open(os.path.join(fresh_logging, logging_setup.LOG_FILENAME),
                encoding="utf-8").read()
    assert "ERROR" in text
    assert "focusguard.monitor" in text


def test_the_log_is_capped_and_rotates(fresh_logging):
    """Unbounded growth was the original problem: ~29,000 lines a day."""
    logger = logging_setup.get_logger("spam")
    for i in range(20000):
        logger.warning("padding line %d %s", i, "x" * 80)

    path = os.path.join(fresh_logging, logging_setup.LOG_FILENAME)
    assert os.path.getsize(path) <= logging_setup.MAX_BYTES * 1.1
    assert os.path.isfile(path + ".1"), "expected a rotated backup"

    total = sum(os.path.getsize(p) for p in logging_setup.log_paths(fresh_logging)
                if os.path.isfile(p))
    cap = logging_setup.MAX_BYTES * (logging_setup.BACKUP_COUNT + 1) * 1.1
    assert total <= cap


def test_debug_detail_is_off_at_the_default_level(data_dir):
    logging_setup.configure(data_dir, level=logging.WARNING, force=True)
    logging_setup.get_logger("monitor").debug("per-poll spam")
    path = os.path.join(data_dir, logging_setup.LOG_FILENAME)
    text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    assert "per-poll spam" not in text


def test_configure_is_idempotent(data_dir):
    logging_setup.configure(data_dir, force=True)
    logging_setup.configure(data_dir)
    assert len(logging.getLogger("focusguard").handlers) == 1


def test_an_unwritable_directory_does_not_crash(tmp_path):
    """An unwritable log location must never stop the app from running."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    logging_setup.configure(str(blocker / "logs"), force=True)
    logging_setup.get_logger("test").warning("still alive")


def test_log_paths_lists_rotated_files(data_dir):
    paths = logging_setup.log_paths(data_dir)
    assert len(paths) == logging_setup.BACKUP_COUNT + 1
    assert paths[0].endswith(logging_setup.LOG_FILENAME)


# ── Deletion covers rotated logs (BL-06 again) ────────────────────────────────

def test_deleting_data_removes_rotated_logs_too(data_dir):
    db = Database(data_dir=data_dir)
    try:
        for path in logging_setup.log_paths(data_dir):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("usage history\n")
        legacy = os.path.join(data_dir, "monitor.log")
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write("pre-1.0 history\n")

        assert db.delete_log_file() is True
        for path in logging_setup.log_paths(data_dir) + [legacy]:
            assert not os.path.exists(path), f"{path} survived deletion"
    finally:
        db.close()


# ── Version single source (ST-07) ─────────────────────────────────────────────

def test_version_is_a_sensible_string():
    assert __version__.count(".") >= 1
    assert all(part.isdigit() for part in __version__.split(".")[:2])
    assert APP_NAME == "FocusGuard"


def test_pyproject_version_matches_the_code():
    """These used to drift silently — two hardcoded copies, no link."""
    assert _pyproject_version() == __version__


def test_the_ui_does_not_hardcode_a_version():
    text = (REPO_ROOT / "ui" / "settings_page.py").read_text(encoding="utf-8")
    assert "from core.version import __version__" in text
    assert '_APP_VERSION = "' not in text


# ── Dependency hygiene (BL-05, ST-07) ─────────────────────────────────────────

def test_pystray_is_gone():
    """
    pystray is LGPL-3.0, which complicates a closed-source frozen build.
    core/tray.py replaces it with ctypes against Win32.
    """
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pystray" not in requirements

    for path in REPO_ROOT.rglob("*.py"):
        if ".git" in str(path) or "tests" in path.parts:
            continue
        assert "import pystray" not in path.read_text(encoding="utf-8"), path


def test_pillow_is_not_a_runtime_dependency():
    """It was only used to draw the tray icon, which now loads from the .ico."""
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pillow" not in requirements


def test_requirements_and_pyproject_agree():
    declared = _pyproject_dependencies()
    listed = {line.split(">")[0].split("=")[0].strip().lower()
              for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")}
    assert declared == listed, f"pyproject {declared} vs requirements {listed}"


def test_debug_scripts_are_not_shipped():
    for name in ("debug.bat", "debug_processes.py", "install.bat", "run.bat"):
        assert not (REPO_ROOT / name).exists(), f"{name} should not ship to users"


# ── Tray degrades safely (BL-05) ──────────────────────────────────────────────

def test_tray_returns_none_when_unavailable():
    """Off Windows there is no tray; main.py already handles None."""
    from core import tray

    result = tray.create_tray(on_show=lambda: None, on_quit=lambda: None)
    assert result is None or hasattr(result, "run")


def test_tray_import_does_not_require_windows():
    import core.tray  # noqa: F401  - importing is the assertion
