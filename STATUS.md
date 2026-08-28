# What's left

Current state and remaining work. `AUDIT.md` is the historical record of what
was found and fixed; this is the forward-looking list.

**Where things stand:** 366 tests green on Python 3.10 and 3.12, lint clean.
Every safety-critical and legal finding from the audit is closed or has its
remaining part named below. What is left splits cleanly into *things only you
can do* and *things anyone can code*.

---

## Blocked on you — nothing can proceed without these

These are the real gates. No amount of coding moves them.

| # | What | Cost | Why it blocks |
|---|---|---|---|
| 1 | **Unlock GitHub billing** | Unknown — check https://github.com/settings/billing | CI has never run. Every check is red, and every job fails with "account is locked due to a billing issue". You are flying blind on every push. |
| 2 | **Microsoft Store developer account** | ~$19 one-time, possibly free now | Microsoft signs Store packages, so **SmartScreen stops warning** — same result as a €300/yr certificate. Also gives you a distribution channel and a payment system. Cheapest unlock on this list by a wide margin. |
| 3 | **Merchant of record** (Paddle or Lemon Squeezy) | ~5% of revenue | The client licensing gate is built. Without this there is nothing to sell keys with. Both handle EU VAT for you. |
| 4 | **A `/license/verify` endpoint** | A morning's work on the server | The client calls it and handles every failure mode. It does not exist. |
| 5 | **Lawyer review of PRIVACY.md, plus ToS and a EULA** | A few hundred euros | The policy is accurate to the code but was not written by a lawyer. You also have no terms and no EULA at all. |
| 6 | **Get the server source into git** | An afternoon | `server/` holds Pydantic models and nothing else. The deployed function holding user emails is unversioned, unreviewed and unbacked-up. |
| 7 | **Trademark-clear the name** | Free (USPTO TESS, EUIPO eSearch) | Cheaper now than after you have users. Also confirm you own the domain. |
| 8 | **A clean Windows VM** | Free | Nothing in `packaging/` or `core/tray.py` has ever run. See below. |

---

## Never been run

Everything Windows-specific was written against documentation and verified only
by tests that read the source. It is very likely something here is wrong.

- **`core/tray.py`** — the whole Win32 tray icon, via ctypes. Degrades to "no
  tray" on failure rather than crashing, so the worst case is a missing icon.
- **`packaging/build.ps1`, `focusguard.spec`, `installer.iss`** — the entire
  build and installer. `build.ps1` launches the frozen app and checks it stays
  running for eight seconds, which is the gate that matters: a missing hidden
  import kills a frozen GUI app *silently*.
- **`core/activity.py`'s two OS probes** — foreground window and idle time. The
  policy they feed is tested; the probes themselves are not.
- **`create_shortcut.ps1`** — rewritten for PowerShell 5.1 but not executed.

The release checklist in `BUILD.md` walks the first real build.

---

## Can be coded now — no external dependency

Roughly in value order.

### 1. API authentication (AUDIT SF-09)
`GET /sync/{device_id}` sends no token. The device ID *is* the credential and
it travels in the URL path, where it lands in server and proxy logs. Anyone
holding or guessing one can read that user's data.

Client-side plumbing is a day. The server half is item 6 above.

### 2. Pin dependencies by hash
`requirements.txt` uses lower bounds, so two builds a month apart are not the
same software. `pip-compile --generate-hashes` before any release.

### 3. Make it an installable package (AUDIT ST-04 remainder)
`main.py` still does `sys.path.insert`. A real `[project.scripts]` entry point
would drop the hack and make the PyInstaller spec simpler.

### 4. Accessibility (AUDIT ST-06 remainder)
DPI awareness and font sizes are fixed. Still missing: keyboard navigation,
screen-reader labelling, a high-contrast mode. The EU Accessibility Act has
applied to consumer software since June 2025.

### 5. Remaining roadmap features
In `ROADMAP.md`, all buildable, none blocking:
pattern recognition over your own history (plain statistics, no model needed),
predictive alerts, PDF/Excel export, team features (needs #1 and sync first).

### 6. Rename to ProtBot
The code says FocusGuard everywhere — `core/version.py`, the tray, the
installer, the `.bat`, the icon, and **the data directory
`%LOCALAPPDATA%\FocusGuard`**.

Not cosmetic. Done properly it needs a migration that moves the old data
directory on first run, care with the Inno `AppId` so updates replace rather
than stack, and ~40 files updated. About an hour. **Much cheaper before anyone
installs than after.**

---

## Known-imperfect, deliberately

Recorded so nobody rediscovers them as bugs.

- **Focus hours is one window, not a scheduler.** Covers work hours, study
  hours, evenings. Multiple named blocks if anyone asks.
- **Client-side licensing is deterrence, not security.** The machine belongs to
  the user. The server is the authority for anything that costs money to
  provide; the client cache is tamper-*evident*, not tamper-proof.
- **The midnight split can misattribute up to one poll interval.** The straddling
  interval goes to the new day. Bounded, and it errs toward the safer side.
- **Premium gates nothing yet.** `_PREMIUM_FEATURES` is deliberately empty — the
  paid tier does not gate a single shipped feature. That is honest, and it is
  also the reason there is nothing to sell.

---

## Suggested order

1. **Billing** — until CI runs you cannot trust any push
2. **Microsoft Store account** — the cheapest thing that removes SmartScreen
3. **First real Windows build** on a clean VM, working through `BUILD.md`
4. **Rename**, if you are going to — before anyone installs
5. **Merchant of record + `/license/verify`** — the last mile to taking money
6. **Lawyer**, before any public release
7. *Then* features, and only then marketing

Steps 1–3 cost almost nothing and unblock everything. Nothing on the feature
list matters until an install completes without a scary warning.
