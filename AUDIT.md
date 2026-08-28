# FocusGuard — Pre-release Readiness Audit

Scope: all 5,395 lines across 26 source files in `Software.zip` (Python 3 / Tkinter / SQLite).
Findings are referenced by ID so they can be tracked as issues.

**Verdict:** the code works. The monitoring loop, session accounting, SQLite layer and
six-tab UI are real, functioning software. The problems are around it — three items create
direct, present legal exposure, and the kill engine can destroy unsaved work or take down
the Windows session.

| Category | Count |
|---|---|
| Legal blockers (BL) | 9 |
| Safety & correctness (SF) | 14 |
| Standards gaps (ST) | 11 |
| Done properly | 7 |

---

## Progress

| ID | Status | What changed |
|---|---|---|
| BL-01 | **Fixed** | `_SAMPLE_ADS` deleted. `_ADS` is empty and the banner does not render without ads. Regression test blocks third-party brands returning to any promotional string |
| BL-02 | **Fixed** | Plan lists cut to shipped features; everything unbuilt moved to `_PLANNED_FEATURES`, rendered greyed out under "Planned" with a "not included in any purchase" note. The Insights teasers no longer show invented statistics as detected findings. Full intent preserved in `ROADMAP.md`. Regression tests block both from returning |
| BL-03 | *Partial* | `PRIVACY.md` written and a first-run consent gate added (`core/consent.py`) — the monitor cannot start until the user accepts, and consent is versioned so a policy change re-prompts. **Still needed:** legal review, terms of service and EULA, a contact address, per-registration consent for the email field, and the server source in version control |
| ST-04 | *Partial* | pytest suite (65 tests), ruff, `pyproject.toml`, and a GitHub Actions workflow across Linux + Windows on Python 3.10 and 3.12. **Still needed:** monitor tests behind a psutil fake, and making the project an installable package instead of `sys.path.insert` |
| ST-07 | *Partial* | Source extracted from `Software.zip` into the repo; `.claude/` and `__pycache__` untracked and gitignored. `debug.bat`, `debug_processes.py`, `install.bat` and `run.bat` no longer ship; `core/version.py` is the single source of truth and a test asserts `pyproject.toml` agrees with it |
| SF-01 | **Fixed** | The kill path is now staged (`core/procutil.py`): the user gets a warning and a 60-second countdown, then WM_CLOSE is posted so the app runs its own save-and-exit path, then a wait, and only what refuses is terminated. Grace period is configurable and floored at 10s |
| SF-02 | **Fixed** | `core/protected.py` denylists Windows critical processes, the shell, Task Manager and other user escape hatches, security software, and FocusGuard's own runtime. Enforced at three layers — the add dialogs, the process matcher, and the terminate call. Task Manager and PowerShell removed from the preloaded catalogue |
| SF-03 | **Fixed** | `create_shortcut.ps1` rewritten for Windows PowerShell 5.1; no PowerShell 7-only operators remain, and failure is now non-fatal to launch |
| SF-06 | **Fixed** | `RLock` around every database read and write, and around the monitor's `active_sessions` / `running_apps` / notification state. Covered by a concurrency test with four writer threads |
| SF-07 | **Fixed** | `PRAGMA user_version` plus a migration runner. A pre-versioning database is adopted rather than rejected, and a database from a newer build raises instead of being silently downgraded |
| SF-11 | **Fixed** | Composite index on `usage_sessions(app_id, date)` and one on `date`. A test asserts via `EXPLAIN QUERY PLAN` that the hot query uses the index rather than scanning |
| SF-12 | **Fixed** | Config writes go to a temp file in the same directory, are fsynced, then `os.replace`d over the target. The previous good copy is kept as `.bak` and used automatically if the live file is ever damaged, so a truncated write no longer resets `device_id` |
| BL-06 | **Fixed** | `delete_all_data()` now clears sessions *and* the tracked-app list, resets autoincrement counters, and VACUUMs; `delete_log_file()` removes the plaintext diagnostic log. The dialog now states exactly what was removed and says plainly that server-side data is not covered |
| SF-04 | **Fixed** | Sessions are split at the date boundary: the old session is closed at 23:59:59 of its own day and a fresh one opened for the new day, so usage stops being filed under the wrong date and the daily counter no longer silently resets mid-session. The split runs *before* the interval is credited — crediting first files post-midnight time under yesterday |
| SF-05 | **Fixed** | `core/activity.py` decides what counts: a gap longer than 1.5x the poll interval is capped (so an overnight sleep credits one interval, not eight hours), time past the idle threshold counts as nothing, and background apps do not accrue when `count_foreground_only` is on. Probes degrade to "cannot tell", in which case time counts rather than silently vanishing |
| SF-10 | **Fixed** | `core/logging_setup.py` — rotating handler capped at 2x512 KB, dated timestamps, levels, and per-poll detail demoted to DEBUG (off by default). `FOCUSGUARD_LOG_LEVEL=DEBUG` turns it up. Rotated backups and the pre-1.0 `monitor.log` are now covered by data deletion |
| SF-13 | **Fixed** | The handlers that hid real failures — UI refresh, device sync, session start/end, shutdown steps — now log with context. The few that remain silent are genuinely optional paths and say so in a comment |
| ST-06 | *Partial* | `SetProcessDpiAwarenessContext` (per-monitor v2, falling back through two older APIs) called before the first Tk window, so the UI is no longer bitmap-stretched on high-DPI displays. 38 instances of 7-8pt text raised to 9pt. **Still needed:** keyboard navigation, screen-reader labelling, and a high-contrast mode |
| BL-05 | **Fixed** | pystray (LGPL-3.0) replaced by `core/tray.py`, ctypes against Shell_NotifyIcon. Also drops Pillow from the runtime — the icon loads from the shipped `.ico` instead of being drawn at startup. Runtime dependencies are now psutil and plyer only, both permissively licensed |
| ST-01 | **Fixed** | `FocusGuard.bat` builds a `.venv` and installs there instead of into the user's global Python, so it can no longer break their other projects. The auto-download of a Python installer is gone entirely. `packaging/focusguard.spec` gives a frozen build with no runtime pip at all |
| ST-02 | *Partial* | `packaging/installer.iss` — per-user Inno Setup installer, stops a running instance before installing, removes the `Run` key on uninstall and offers to delete `%LOCALAPPDATA%\FocusGuard`. `packaging/build.ps1` runs tests and lint, generates the Windows version resource from `core/version.py`, builds, **smoke-tests that the frozen app stays running**, and signs with timestamping when a certificate is supplied. **Still needed:** an actual certificate, a first real Windows build, and an update mechanism |
| ST-03 | **Fixed** | All three antivirus triggers removed from the launcher: no global pip, no downloading and executing an unverified `.exe`, no `-ExecutionPolicy Bypass`. Build is one-folder rather than one-file (one-file unpacks to `%TEMP%` on every launch) and UPX is off. Tests fail the build if any of them return |
| SF-11 | **Fixed** | Indices were added earlier; retention now closes the other half. `retention_days` defaults to 365 (0 keeps everything), pruned on the daily rollover rather than at startup so launch stays fast, and exposed in Settings — `PRIVACY.md` says the user can change it there, so a test asserts the control exists |
| SF-08 | *Partial* | The `plan = "premium"` override is gone and the editable `plan` key with it. `core/licensing.py` is now the single gate: entitlement is cached signed and machine-bound, so hand-editing `config.json` invalidates it rather than granting premium; a verified licence survives 14 days offline so a dropped connection never revokes a paying customer; and a server error leaves the cached entitlement alone. `_activate_license` is a real flow off the UI thread. **Still needed:** the `/license/verify` endpoint and a merchant of record — those are the only missing pieces now |
| SF-14 | **Fixed** | Kill watcher is now joined on `stop()`; `_notified_limits` resets on date rollover so warnings resume after day one; the `sound` parameter that was accepted and ignored is gone, and the sound setting now actually plays |

**On what client-side licensing can do** — this is desktop software, so a
determined user can always patch the binary. `core/licensing.py` says so in its
docstring rather than pretending otherwise, and splits the problem: the server
is the authority for anything that costs money to provide (sync, hosted
storage), gated at the point of use; the client cache is *tamper-evident*, not
tamper-proof, which stops casual config editing — the realistic case — and
claims nothing more.

**New since the audit** — `core/updates.py` adds an update check, which the
original review flagged as missing entirely: without one, a security fix can
never reach anyone who has already installed. It reads a static JSON manifest
(hostable free, no backend), compares versions numerically rather than as
strings, refuses a non-https download URL because the manifest is untrusted
network input, and never downloads or installs anything itself.

**Found while fixing the above** — three network error paths in
`ui/devices_page.py` referenced `exc` inside a lambda scheduled with
`after()`. Python deletes that binding when the `except` block exits, so every
registration or device-link failure raised `NameError` instead of showing the
error. Fixed by binding the value into the lambda's default argument.

---

## Section A — Legal exposure

### BL-01 · CRITICAL · Unauthorized ads for Notion, GitHub and Endel
`ui/app.py:281-301` — `_SAMPLE_ADS`

The ad banner ships three hardcoded ads using real companies' trademarks and their actual
marketing taglines, each linking to their live site. The code calls them placeholders, but a
placeholder that ships to users is published commercial content. Implies a commercial
relationship that does not exist — false endorsement under Lanham Act §43(a) in the US, a
misleading commercial practice in the EU/UK.

**Fix:** delete `_SAMPLE_ADS` entirely. Ship the banner hidden until a real ad network is wired up.

### BL-02 · CRITICAL · Premium plan advertises six features that do not exist
`ui/devices_page.py:42-66`

Advertised but absent from the codebase: AI pattern recognition, predictive distraction
alerts, PDF/Excel export, team challenges & leaderboards, unlimited data retention, 4-week
free-tier retention. There is no retention logic of any kind on either tier. The free tier's
"12 apps" and "2 devices" caps are never enforced.

**Fix:** cut the list to what runs today; move anything planned under a separate "Coming soon" heading.

### BL-03 · CRITICAL · Personal data sent with no privacy policy, notice or consent
`ui/devices_page.py:471-489`, `core/config.py:21`

Registration sends the user's email address and machine hostname to a US Firebase endpoint.
The app also accumulates behavioral usage data. No privacy policy, terms, EULA, consent
checkbox, or disclosure exists — a missing GDPR Art. 13 notice and Art. 6 legal basis
simultaneously. The "email discarded immediately" claim lives only in a code comment, and the
server that would honor it is not in this repository.

**Fix:** privacy policy + terms + EULA before any public build; first-run consent screen;
make email explicitly optional; get the server source into version control.

### BL-04 · CRITICAL · Force-kill with no warning will destroy user work
See SF-01. Belongs on the legal list because no EULA disclaimer fully insulates against a
consumer-law claim in the EU/UK for foreseeable damage caused by the product working as designed.

### BL-05 · HIGH · pystray is LGPL-3.0
`requirements.txt:2` — verified against PyPI metadata

psutil (BSD-3), plyer (MIT) and Pillow (HPND) are fine. pystray is LGPL-3.0: statically
bundling it into a one-file PyInstaller build of a proprietary product triggers LGPL §4.

**Fix:** PyInstaller *one-folder* build so pystray stays separable, or swap for an MIT/BSD tray
implementation, or call the Win32 shell-notify API directly. Ship `THIRD-PARTY-LICENSES.txt` either way.

### BL-06 · HIGH · "Delete All Data" does not delete all data
`core/database.py:254-256`, `ui/settings_page.py:340`

Runs `DELETE FROM usage_sessions` only. Leaves `tracked_apps`, `monitor.log` (a plaintext
record of every app opened), and all server-side data — for which no deletion endpoint exists.
GDPR Art. 17 failure, and a false statement in the UI.

### BL-07 · HIGH · No LICENSE file, no decision about what this software is
Public repo with no license = all-rights-reserved by default, while the full source is
cloneable by anyone. Pick a lane: private repo + proprietary EULA with the binary, or
open-source and monetize the hosted sync.

### BL-08 · HIGH · Student market pulls in children's privacy law
A focus/screen-time app markets to students. Collecting email + behavioral data from a US
user under 13 engages COPPA (verifiable parental consent, fines per child). GDPR Art. 8 sets
the EU digital-consent floor at 13-16 depending on member state.

**Fix:** minimum age in the terms, neutral age gate at first run, no email below the threshold.

### BL-09 · MEDIUM · Name clearance and third-party monitoring
- "FocusGuard" is uncleared — run USPTO TESS and EUIPO eSearch before spending on branding.
  Confirm you own `focusguard.app` (the upgrade button opens it).
- The app can be installed on a machine another person uses and silently records them once
  minimized to tray. Engages monitoring-consent and two-party consent law. Keep the tray icon
  permanently visible; state in the terms that FocusGuard is for monitoring your own device.

---

## Section B — Safety and correctness

### SF-01 · CRITICAL · Kill path is a hard TerminateProcess with zero grace
`core/monitor.py:361-385`

`proc.kill()` maps to `TerminateProcess` on Windows. No shutdown message, no flush, no save
prompt, and no warning countdown — the kill watcher fires the moment the threshold is crossed.

**Fix:** stage it. Notify at T-60s with a visible countdown → post `WM_CLOSE` to top-level
windows → wait 10s → terminate as last resort, and log that you had to.

### SF-02 · CRITICAL · Nothing stops the app killing critical Windows processes
`core/apps_list.py:938-955`, `ui/files_page.py:312`

No denylist anywhere. "Add by file" accepts any executable including `csrss.exe`,
`winlogon.exe`, `lsass.exe`, `services.exe` — terminating one triggers a
`CRITICAL_PROCESS_DIED` bugcheck. Not hypothetical: the preloaded catalogue ships **Task
Manager** and **PowerShell** as targets. Limit Task Manager with auto-kill on and the 5-second
watcher kills it every time the user opens it, locking them out of the tool they'd use to stop
FocusGuard.

**Fix:** hardcode a system-binary denylist; remove the System category from the preloaded list.

### SF-03 · CRITICAL · Shortcut script cannot run on stock Windows
`create_shortcut.ps1:3`

```powershell
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue)?.Source
```

`?.` requires PowerShell 7. Windows 10/11 ship Windows PowerShell 5.1, and the batch file
invokes `powershell`, which always resolves to 5.1. Parse error → every user on a stock
install gets no desktop shortcut plus a red error dump. Works locally only because PS7 is installed.

**Fix:** rewrite for 5.1 and test the install flow in a clean Windows VM.

### SF-04 · HIGH · Sessions never split at midnight
`core/database.py:140-148`

`start_session` stamps `date` from the start time and never changes it. A 23:50→02:00 session
files all 130 minutes under yesterday. `get_today_usage_sec` queries `WHERE date = today`, so
at midnight the running session becomes invisible and the counter silently resets — a free
unlimited window until the app is closed and reopened.

### SF-05 · HIGH · No idle or sleep detection (the laptop-lid bug)
`core/monitor.py:328-334`

Duration is pure wall-clock between polls. Chrome open + lid shut overnight = eight hours of
"usage", and with auto-kill on it dies the instant you resume.

**Fix:** track the foreground window via `GetForegroundWindow`; detect resume-from-sleep by
comparing wall-clock elapsed against the expected poll interval and discard the difference.

### SF-06 · HIGH · Three threads share a SQLite connection and a dict with no locking
`core/database.py:49`, `core/monitor.py:65`

`check_same_thread=False` silences Python's safety check without providing safety. Monitor
thread, 5-second kill watcher, Tk main thread and ad-hoc network threads all write through it.
There is not a single lock in the codebase; `active_sessions` is mutated from two threads.
Expect intermittent `ProgrammingError`, lost session rows and double-counted durations.

**Fix:** `threading.RLock` around every DB method plus a separate lock for `active_sessions`,
or move all DB access onto a single writer thread fed by a queue.

### SF-07 · HIGH · No database schema versioning
`core/database.py:56-59`

`CREATE TABLE IF NOT EXISTS` and nothing else. Adding a column in v1.1 breaks every existing
install. Set `PRAGMA user_version` now while it's free, and add a migration runner.

### SF-08 · HIGH · Monetization is switched off in code and unenforceable by design
`core/config.py:49-50`, `ui/devices_page.py:691-699`

```python
# Always force premium so Pro features are available for testing
self._data["plan"] = "premium"
```

Every install is unconditionally Premium. Even without that line, `plan` lives in a plaintext
JSON file the user can edit in Notepad, and every gate reads it client-side with no server
check. `_activate_license` is a stub. There is currently no path by which this product can
take money.

**Fix:** delete the override; move entitlement server-side keyed on device ID, verified at
startup and cached with a short expiry; integrate Paddle or Lemon Squeezy (merchant of record,
handles EU VAT).

### SF-09 · HIGH · Sync API has no authentication
`ui/processes_page.py:302-304`, `ui/devices_page.py:69-84`

`GET /sync/{device_id}` sends no token, no signature, no header. The device ID *is* the
credential and it travels in the URL path, where it lands in server, proxy and intermediary
logs. Textbook IDOR.

**Fix:** issue a secret token at registration, send as `Authorization` header, keep device IDs
out of URL paths, rate-limit the link-code endpoint.

### SF-10 · MEDIUM · Log grows forever and records everything
`core/monitor.py:147-154, 272-273`

One line per tracked app per poll, no rotation, no cap — ~28,800 lines/day with 20 apps on a
60s interval. Unencrypted plaintext behavioral record in `%LOCALAPPDATA%`, untouched by
"Delete All Data" (BL-06). Timestamps are `%H:%M:%S` with no date, making the log useless
across days.

**Fix:** `RotatingFileHandler` with a few MB cap, add the date, drop per-app spam to DEBUG,
default release builds to WARNING.

### SF-11 · MEDIUM · No indices, no retention
No index on `usage_sessions(app_id, date)`, so every `get_today_usage_sec` is a full table
scan — called once per tracked app every five seconds by the kill watcher, against a table
that grows without bound.

**Fix:** add the composite index plus one on `date`; implement the retention tiers you already
advertise (also fixes half of BL-02).

### SF-12 · MEDIUM · Config writes are not atomic
`core/config.py:60-65`

`json.dump` writes straight over the live file. Crash mid-write → truncated `config.json` →
parse failure → every setting silently resets to defaults, including `device_id`, orphaning
the user's server-side data. Reachable from multiple threads with no lock, and
`except OSError: pass` makes a failed write invisible.

**Fix:** temp file in the same directory + `os.replace`, guarded by a lock; keep one backup.

### SF-13 · MEDIUM · Twenty silent exception handlers in the monitor alone (53 codebase-wide)
The dominant pattern is `except Exception: pass`. Failed session starts, failed DB writes and
throwing callbacks are all invisible. The app carries on appearing to work while losing data.

**Fix:** every handler logs with context or re-raises; reserve silent swallowing for genuinely
optional paths.

### SF-14 · MEDIUM · Four smaller defects to batch
- **Naive local time for durations** (`monitor.py` throughout) — DST transitions yield
  durations an hour off, or negative. Use `time.monotonic()` for elapsed, store UTC.
- **`_notified_limits` never resets** (`monitor.py:72`) — nothing clears it at midnight, so
  warnings stop firing after day one until restart.
- **Kill watcher never joined** (`monitor.py:110-111`) — `stop()` joins `_thread` but not
  `_kill_thread`, so a kill can fire during shutdown after sessions are closed.
- **Kills match by name across all processes** (`monitor.py:376`) — every process with a
  matching name dies, including other users' on a shared machine. Prefer path matching.

---

## Section C — Distribution and engineering standards

### ST-01 · CRITICAL · Launcher installs packages into the user's global Python at every startup
`FocusGuard.bat:64-68`

`pip install -r requirements.txt` runs on every launch against system-wide Python with
`>nul 2>&1` hiding errors. It can upgrade/downgrade packages other projects depend on;
requirements are pinned with `>=` and no hashes, so a compromised PyPI release executes on the
user's machine; and if both pip attempts fail the script launches anyway and the app dies silently.

**Fix:** stop installing at runtime — ship a frozen build. Until then, a virtualenv inside the
app directory with exact pinned versions and hashes.

### ST-02 · CRITICAL · No code signing, no installer, no auto-update
Distribution is a zip of Python source plus a `.bat`. Unsigned → SmartScreen warning, which
ends most installs for an app that reads your process list. No MSI/Inno package, no
uninstaller (registry Run key, desktop shortcut and `%LOCALAPPDATA%\FocusGuard` all survive
deletion), and no update mechanism — you can never push a security fix to an existing install.

**Fix:** PyInstaller → Inno Setup → code-signing certificate (~$200-400/yr, or Azure Trusted
Signing). Add a version-endpoint update check and a proper uninstall entry.

### ST-03 · HIGH · Install script looks like malware to AV heuristics
`FocusGuard.bat:44-50, 83`

Four behaviors scored together: `-ExecutionPolicy Bypass`; downloading and executing an `.exe`
with no hash verification; enumerating all processes; terminating processes — including Task
Manager (SF-02). Add an unsigned binary and a registry Run key for persistence and you have
most of a generic-trojan signature.

**Fix:** drop `ExecutionPolicy Bypass`; remove the runtime Python download (ST-01 makes it
unnecessary); fix SF-02; sign the binary; submit to Microsoft and major vendors for
whitelisting before launch.

### ST-04 · HIGH · No tests, no CI, no linting, no packaging metadata
Zero test files, no CI config, no `pyproject.toml`, no linter/formatter config, no type
checking. `main.py` uses `sys.path.insert` instead of being an installable package. Committed
`__pycache__` shows Python 3.7 compilation while the launcher installs 3.12 and the README
asks for 3.10+ — three implied targets, none tested.

**Fix:** pytest around session accounting and limit logic (exactly where SF-04 and SF-05 hid),
ruff, a `pyproject.toml` declaring one supported version, GitHub Actions on push.

### ST-05 · MEDIUM · The backend is not in version control
`server/` holds only Pydantic models. The deployed Cloud Function holding user emails and
usage history is unversioned, unreviewed and unbacked-up. Also `requirements.txt` omits
`pydantic`, which `models.py` imports — this directory cannot run as checked in.

### ST-06 · MEDIUM · Accessibility and display quality
Tkinter is not DPI-aware by default → blurry, undersized UI on high-DPI laptops. Body text is
8-9pt in several places. Hardcoded hex colors with no high-contrast mode, no keyboard
navigation, no screen-reader labelling. The EU's European Accessibility Act has applied to
consumer software since June 2025.

**Fix:** `SetProcessDpiAwareness` at startup, 10pt minimum, colors into a theme module, every
control keyboard-reachable with a visible focus ring.

### ST-07 · MEDIUM · Housekeeping
- Debug files ship to users: `debug.bat`, `debug_processes.py`, `install.bat`, `run.bat`.
  `install.bat` duplicates the dependency list from `requirements.txt` and will drift.
- `.claude/settings.local.json` was committed despite being gitignored (leaks a local path);
  `__pycache__` too. `git rm -r --cached` both.
- Version string hardcoded at `ui/settings_page.py:22` with no single source of truth.

---

## Scorecard

| Capability | Status | Reality |
|---|---|---|
| Process detection | **Done** | Matches on name and full path, handles psutil absence gracefully |
| SQLite storage layer | **Done** | Parameterised throughout, WAL mode, foreign keys on |
| Six-tab UI | **Done** | Complete; correctly marshals to the Tk thread via `after()` |
| Preloaded app catalogue | **Done** | 100 apps with real install-path hints |
| Insights & charts | **Done** | Peak hours, categories, top apps — computed from real data |
| Tray + startup integration | **Done** | Correct HKCU Run key usage, clean tray behavior |
| CSV export | **Done** | The only export feature that exists |
| Usage time accounting | *Partial* | Wrong across midnight (SF-04) and during sleep (SF-05) |
| Auto-kill enforcement | *Partial* | Fires reliably, but unsafely (SF-01) with no guardrails (SF-02) |
| Notifications | *Partial* | Stop firing after day one (SF-14); `sound` param accepted and ignored |
| Device registration & sync | *Partial* | Client written; server unversioned (ST-05), unauthenticated (SF-09) |
| Data deletion | *Partial* | Sessions only; leaves apps, logs, server data (BL-06) |
| Free/Premium tiers | **Missing** | Hardcoded Premium, no caps, no server check, no payment path |
| Six advertised Premium features | **Missing** | None exist in code (BL-02) |
| Legal documents | **Missing** | No privacy policy, terms, EULA or license |
| Installer & code signing | **Missing** | Zip + `.bat`; SmartScreen will block it |
| Update mechanism | **Missing** | No way to ship a fix to an existing install |
| Uninstaller | **Missing** | Registry key, shortcut and data directory persist |
| Tests & CI | **Missing** | Zero test files, no pipeline, no linting |
| Schema migrations | **Missing** | v1.1 breaks every existing database (SF-07) |
| Crash reporting | **Missing** | 53 silent handlers; failures never reach you |

---

## What you got right

- **Every SQL query is parameterised.** Not one string-formatted query in 270 lines of
  database code — the most common vulnerability in hobby projects, and it simply isn't here.
- **Thread-to-UI marshalling is correct.** The monitor fires callbacks on its own thread and
  the UI consistently bounces them through `root.after()`.
- **Sessions are checkpointed mid-flight** so a crash doesn't lose the current session.
- **Data lives in `%LOCALAPPDATA%`**, the correct Windows convention — no admin rights needed.
- **Optional dependencies degrade gracefully.** Missing psutil, pystray or plyer disables a
  feature instead of crashing.
- **The payload protocol is deliberately efficient** — single-char JSON keys, 30-minute
  batching, only non-zero entries uploaded.
- **The preloaded catalogue is real work** — 100 apps across twelve categories.

---

## Ordered plan

### Phase 0 — Today (hours)
- [ ] Delete `_SAMPLE_ADS` (Notion/GitHub/Endel) from the repository — BL-01
- [ ] Cut the fake feature list down to what the code does — BL-02
- [ ] Add a system-process denylist; remove Task Manager and PowerShell from the catalogue — SF-02
- [ ] Remove the `plan = "premium"` override — SF-08
- [ ] Untrack `.claude/` and `__pycache__` — ST-07

### Phase 1 — Make the core feature safe (1 week)
- [ ] Rebuild the kill path in stages: countdown → `WM_CLOSE` → wait → terminate — SF-01/BL-04
- [ ] Split sessions at midnight — SF-04
- [ ] Foreground-window and sleep detection — SF-05
- [ ] Lock the database and the shared session dict — SF-06
- [ ] Fix `create_shortcut.ps1` for PowerShell 5.1; test on a clean VM — SF-03
- [ ] Atomic config writes — SF-12

### Phase 2 — Legal foundation (1 week + review)
- [ ] Privacy policy, terms of service, EULA — draft from a template, then lawyer review — BL-03
- [ ] First-run consent screen, email clearly optional — BL-03
- [ ] Make "Delete All Data" complete, including log file and server records — BL-06
- [ ] Resolve pystray LGPL; ship `THIRD-PARTY-LICENSES.txt` — BL-05
- [ ] Age gate + minimum age in the terms — BL-08
- [ ] Choose licensing model; add `LICENSE` — BL-07
- [ ] Trademark-clear the name; confirm domain ownership — BL-09

### Phase 3 — Make it distributable (2 weeks)
- [ ] PyInstaller build + Inno Setup installer + uninstaller — ST-01/ST-02
- [ ] Code-signing certificate; sign every release — ST-02
- [ ] Update check — ST-02
- [ ] Submit to Microsoft and AV vendors for whitelisting — ST-03
- [ ] Schema versioning and migration runner — SF-07
- [ ] Real logging with rotation and dates — SF-10/SF-13
- [ ] DPI awareness and minimum font size — ST-06

### Phase 4 — Make it able to take money (2 weeks)
- [ ] Commit the server source; put it under CI — ST-05
- [ ] API authentication; device IDs out of URL paths — SF-09
- [ ] Server-side entitlement checks — SF-08
- [ ] Paddle or Lemon Squeezy integration — SF-08
- [ ] Enforce free-tier caps; implement retention tiers — BL-02/SF-11
- [ ] Database indices — SF-11

### Phase 5 — Keep it from regressing (ongoing)
- [ ] pytest around session accounting and limit logic — ST-04
- [ ] ruff, `pyproject.toml`, one Python version, GitHub Actions — ST-04
- [ ] Opt-in crash reporting — SF-13
- [ ] Then build the advertised features — and only advertise them once they run

---

Legal points are engineering observations about what the code does and which regimes it
touches — not legal advice. The Phase 2 items are where a qualified lawyer's few hours are
worth paying for.
