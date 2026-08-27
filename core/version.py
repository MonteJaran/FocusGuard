"""
version.py - The single source of truth for FocusGuard's version.

Everything that displays or reports a version imports from here. It used to be
hardcoded in ui/settings_page.py and duplicated in pyproject.toml, which drifts
silently the first time one is bumped without the other; a test asserts the two
now agree.
"""

__version__ = "1.0.0"

APP_NAME = "FocusGuard"
