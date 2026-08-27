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
| `test_protected.py` | The denylist that stops FocusGuard closing critical Windows processes or Task Manager |
| `test_procutil.py` | The staged close sequence, against a faked psutil — no real processes are touched |
| `test_monitor_grace.py` | The warning countdown before an app is closed, and the daily rollover reset |
| `test_storage_hardening.py` | Schema versioning, index usage, complete deletion, atomic config writes, concurrent writers |
| `test_activity.py` | The accounting rules — sleep caps, idle, foreground — as pure functions |
| `test_monitor_polling.py` | The polling loop end to end, with psutil, the clock and the activity probes all faked |
| `test_logging_and_packaging.py` | Log rotation and format, the version single-source, and dependency hygiene |
| `test_packaging_build.py` | The PyInstaller spec, installer script and launcher — drift and antivirus-trigger regressions |
| `test_retention_and_updates.py` | History pruning, version comparison, manifest handling, and that the privacy policy matches the product |

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

There are none right now. `test_delete_all_data_also_clears_tracked_apps` used
to be `xfail(strict=True)` documenting AUDIT BL-06; when the fix landed the
test started passing and `strict=True` failed the build until the marker was
removed. That is the intended lifecycle — a marker is a reminder, not a
permanent exemption.

## Safety tests

`test_protected.py` and `test_procutil.py` cover behaviour that damages a
user's machine when it goes wrong: terminating a Windows critical process
bugchecks the box, and terminating without warning destroys unsaved work.
`test_procutil.py` fakes psutil rather than starting real processes, so the
close sequence can be asserted step by step without side effects.

## The polling harness

`test_monitor_polling.py` fakes psutil, `time.monotonic`, `datetime.now` **and**
`database.date.today` together. That last one matters: the monitor and the
database each decide "today" independently, so faking only one leaves them
disagreeing and every date-filtered query silently returns nothing.

With all four faked, a session running past midnight or a machine asleep for
eight hours is reproducible exactly, in milliseconds, with no real clock
involved. That is how SF-04 and SF-05 were fixed — and the harness caught a
real ordering bug along the way: crediting time before splitting at midnight
files post-midnight usage under yesterday.

## Not covered yet

The Tk UI modules are not imported by the suite because CI runners have no
display; the `syntax` CI job byte-compiles them instead.

`core/tray.py` is Win32-only and cannot be exercised here — the tests confirm
it imports and degrades to None off Windows, but the icon itself needs a real
Windows box.
