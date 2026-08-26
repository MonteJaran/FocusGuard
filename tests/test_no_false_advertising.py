"""
Regression guards for the two findings that carry legal exposure.

These parse the source with `ast` rather than importing it, so they run on a
CI box with no display and no Tk. They are deliberately blunt: it is much
cheaper to fail a build than to answer a letter.

  * AUDIT BL-01 — third-party brands were shipped in the in-app ad slot
  * AUDIT BL-02 — the plan comparison advertised features that did not exist
"""

import ast
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# core/apps_list.py is exempt from the brand scan below. It is a catalogue of
# applications the user can choose to track, and naming a product in order to
# identify it is ordinary descriptive use. Naming one in an advertising slot is
# a different thing entirely — that is what the scan is for.
BRAND_SCAN_EXEMPT = {os.path.join("core", "apps_list.py")}

SOURCE_FILES = [
    os.path.join(dirpath, name)
    for dirpath, _dirs, files in os.walk(REPO_ROOT)
    for name in files
    if name.endswith(".py")
    and ".git" not in dirpath
    and f"{os.sep}tests" not in dirpath
]

BRAND_SCAN_FILES = [
    p for p in SOURCE_FILES
    if os.path.relpath(p, REPO_ROOT) not in BRAND_SCAN_EXEMPT
]


def _module(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _assign(tree, name):
    """Return the value node assigned to a module-level `name`, or None."""
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign)
                   else [])
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
    return None


def _string_constants(node):
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


# ── BL-01: no third-party brands in the ad slot ───────────────────────────────

# Brands that were previously shipped as "placeholder" ads. Putting a real
# company in an ad slot implies a commercial relationship that does not exist.
# Any placeholder must be an invented brand.
FORBIDDEN_BRANDS = [
    "notion", "copilot", "endel", "github.com/features",
    "todoist", "evernote", "grammarly", "spotify",
]


def test_ad_list_is_empty():
    tree = _module(os.path.join(REPO_ROOT, "ui", "app.py"))
    ads = _assign(tree, "_ADS")
    assert ads is not None, "ui/app.py must define _ADS"
    assert isinstance(ads, (ast.List, ast.Tuple)), "_ADS must be a literal list"
    assert ads.elts == [], (
        "_ADS must stay empty until a real ad network is integrated. "
        "See AUDIT.md BL-01."
    )


def test_the_old_sample_ads_are_gone():
    tree = _module(os.path.join(REPO_ROOT, "ui", "app.py"))
    assert _assign(tree, "_SAMPLE_ADS") is None, (
        "_SAMPLE_ADS shipped real companies' trademarks and taglines. "
        "It must not come back."
    )


@pytest.mark.parametrize("path", BRAND_SCAN_FILES,
                         ids=lambda p: os.path.relpath(p, REPO_ROOT))
def test_no_third_party_brand_strings_in_source(path):
    """
    No shipped string outside the tracking catalogue may name a third-party
    brand. Naming an app so the user can track it is fine; putting a brand
    anywhere that reads as promotion is not.
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)

    for text in _string_constants(tree):
        lowered = text.lower()
        for brand in FORBIDDEN_BRANDS:
            assert brand not in lowered, (
                f"{os.path.relpath(path, REPO_ROOT)} contains the brand "
                f"{brand!r} in a string literal: {text[:80]!r}. See AUDIT.md BL-01."
            )


# ── BL-02: only advertise features that exist ─────────────────────────────────

def _plan_lists():
    tree = _module(os.path.join(REPO_ROOT, "ui", "devices_page.py"))
    return (
        _string_constants(_assign(tree, "_FREE_FEATURES")),
        _string_constants(_assign(tree, "_PREMIUM_FEATURES")),
        _string_constants(_assign(tree, "_PLANNED_FEATURES")),
    )


def test_plan_lists_exist():
    free, premium, planned = _plan_lists()
    assert isinstance(free, list) and isinstance(premium, list)
    assert planned, "_PLANNED_FEATURES records what is still to be built"


def test_planned_features_are_not_also_sold():
    """Nothing may appear as both 'planned' and 'included'."""
    free, premium, planned = _plan_lists()
    sold = {f.lower() for f in free + premium}
    for feature in planned:
        assert feature.lower() not in sold, (
            f"{feature!r} is listed as planned and as included. "
            "A feature is one or the other. See AUDIT.md BL-02."
        )


# Features that were advertised while no code implemented them. Each may only
# move into the sold lists once it genuinely works end to end.
UNIMPLEMENTED_CLAIMS = [
    "ai pattern recognition",
    "predictive distraction alerts",
    "pdf / excel report export",
    "team challenges",
    "unlimited data retention",
    "4 weeks data retention",
    "priority support",
]


def test_unimplemented_features_are_not_advertised_as_included():
    free, premium, _planned = _plan_lists()
    sold = " | ".join(free + premium).lower()
    for claim in UNIMPLEMENTED_CLAIMS:
        assert claim not in sold, (
            f"{claim!r} is advertised as an included feature but is not "
            "implemented. Move it to _PLANNED_FEATURES. See AUDIT.md BL-02."
        )


def test_retention_is_not_advertised_until_it_is_implemented():
    """There is no pruning logic anywhere yet, so no tier may promise one."""
    free, premium, _planned = _plan_lists()
    sold = " | ".join(free + premium).lower()
    assert "retention" not in sold, (
        "No retention logic exists in the codebase (AUDIT SF-11), so no plan "
        "may advertise a retention window."
    )
