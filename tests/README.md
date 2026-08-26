# Tests

```bash
python -m pip install pytest ruff
python -m pytest          # run the suite
python -m ruff check .    # lint
```

Every test runs against a temp directory, so the suite never touches your real
`%LOCALAPPDATA%\FocusGuard` data.

## What's covered

| File | Covers |
|---|---|
| `test_database.py` | App records, session lifecycle, usage aggregation, persistence, SQL-injection round-trip |
| `test_config.py` | Defaults, persistence, merging new keys into an old config, recovery from a corrupt file |
| `test_consent.py` | The first-run privacy gate's decision logic and policy versioning |
| `test_no_false_advertising.py` | Regression guards for the two legal findings — see below |

## The regression guards

`test_no_false_advertising.py` is not a normal unit test. It parses the source
with `ast` and fails the build if either of two problems comes back:

- **BL-01** — a third-party brand appears in a string outside the app catalogue.
  The app previously shipped ads for real companies using their own taglines.
  `core/apps_list.py` is exempt: naming an app so the user can track it is
  ordinary descriptive use; naming one in an ad slot is not.
- **BL-02** — a feature is advertised in the plan comparison while no code
  implements it. Anything unbuilt belongs in `_PLANNED_FEATURES`, which renders
  greyed out under a "Planned" heading.

Both are cheap to check and expensive to get wrong, which is why they are
enforced by the build rather than by memory.

## Known-failure markers

`test_delete_all_data_also_clears_tracked_apps` is `xfail(strict=True)`. It
documents AUDIT BL-06 — "Delete All Data" does not delete everything it claims
to. When that is fixed the test starts passing, and `strict=True` makes the
build fail until the marker is removed. The marker is a reminder, not a
permanent exemption.

## Not covered yet

The Tk UI modules are not imported by the suite because CI runners have no
display; the `syntax` CI job byte-compiles them instead. `core/monitor.py`
needs a psutil fake before it can be tested properly — worth doing, since
AUDIT SF-04 (midnight rollover) and SF-05 (sleep detection) are exactly the
kind of bug a unit test catches.
