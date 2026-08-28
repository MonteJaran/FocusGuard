"""The privacy consent gate.

The dialog itself needs a display, so these cover the decision logic that
main.py branches on — the part that decides whether anything gets recorded.
"""

import os

from core import consent
from core.consent import (
    CONSENT_VERSION,
    has_consented,
    policy_path,
    record_consent,
    revoke_consent,
)


def test_fresh_install_has_not_consented(config):
    assert has_consented(config) is False


def test_accepting_records_consent(config):
    record_consent(config, True)
    assert has_consented(config) is True
    assert config.get("consent_accepted") is True
    assert config.get("consent_version") == CONSENT_VERSION
    assert config.get("consent_at")           # timestamped


def test_declining_does_not_record_consent(config):
    record_consent(config, False)
    assert has_consented(config) is False
    assert config.get("consent_accepted") is False
    assert config.get("consent_at") == ""


def test_consent_survives_a_restart(data_dir):
    from core.config import Config

    record_consent(Config(data_dir=data_dir), True)
    assert has_consented(Config(data_dir=data_dir)) is True


def test_revoking_re_arms_the_gate(config):
    record_consent(config, True)
    revoke_consent(config)
    assert has_consented(config) is False
    assert config.get("consent_at") == ""


def test_a_new_policy_version_re_prompts(config):
    """Raising CONSENT_VERSION must ask everyone again."""
    record_consent(config, True)
    assert has_consented(config) is True

    config.set("consent_version", CONSENT_VERSION - 1)
    assert has_consented(config) is False


def test_missing_key_is_treated_as_no_consent(config):
    config.set("consent_version", None)
    assert has_consented(config) is False


def test_policy_file_ships_with_the_app():
    assert os.path.isfile(policy_path()), "PRIVACY.md must ship alongside the app"


def test_policy_summary_states_what_is_not_collected():
    """The summary is the only privacy text most users will read."""
    summary = consent._SUMMARY.lower()
    for claim in ("keystrokes", "screenshots", "browsing history"):
        assert claim in summary
    assert "stays on your computer" in summary
