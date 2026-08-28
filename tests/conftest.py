"""Shared fixtures. Every test runs against a temp directory, never the real
%LOCALAPPDATA%, so running the suite can't touch a developer's own data."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config          # noqa: E402
from core.database import Database      # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "FocusGuard")


@pytest.fixture
def db(data_dir):
    database = Database(data_dir=data_dir)
    yield database
    database.close()


@pytest.fixture
def config(data_dir):
    return Config(data_dir=data_dir)
