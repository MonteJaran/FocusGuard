# FocusGuard Roadmap

Where planned features live so they are not forgotten — and so they stay **out**
of the marketing surface until they actually work.

## The rule

A feature may only appear in `_FREE_FEATURES` or `_PREMIUM_FEATURES`
(`ui/devices_page.py`) once it works end to end in the shipped build.

Everything else goes in `_PLANNED_FEATURES`, which renders greyed out under a
"Planned" heading with a "not included in any purchase" note. Selling a feature
that does not exist is deceptive advertising, and becomes a refund and
chargeback problem the moment the app takes money.

When a feature ships, move it up the list here **and** in `devices_page.py`.

---

## Planned Premium features

These are the features that were previously advertised as if they existed. They
are the intended Premium tier — kept here in full so the plan survives.

### 1. Cross-device sync
Usage totals aggregated across every linked device, so a daily limit applies to
you rather than to one machine.

- **Status:** client-side plumbing exists (`ui/devices_page.py`,
  `ui/processes_page.py`, `server/models.py`), server is unversioned
- **Blocked on:** committing the backend to this repo (AUDIT ST-05) and adding
  API authentication (AUDIT SF-09)
- **Notes:** device registration, 8-char link codes and the 30-minute upload
  protocol are already designed and partly built

### 2. Configurable data retention — SHIPPED

- **Status:** done. `retention_days` defaults to 365; 0 keeps everything.
  Pruning runs on the daily date rollover the monitor already detects, not at
  startup, so launch stays fast.
- **Note:** this is now a plain user setting rather than a paid tier. Making
  someone pay to keep their own history is a poor trade, and the database
  indices (SF-11) solved the performance half of the problem anyway.

### 3. Pattern recognition across your history
Surface real patterns from recorded usage: which app tends to precede a long
distraction session, which days drift worst, how a week compares to the last.

- **Status:** not started
- **Blocked on:** retention (needs enough history to be meaningful)
- **Notes:** was advertised as "AI pattern recognition". Start with plain
  statistics over the existing `usage_sessions` table — week-over-week deltas,
  correlation between app launches, time-of-day clustering. That is genuinely
  useful and needs no model. Only call it AI if a model is actually involved


### 4. Predictive distraction alerts
Warn *before* a distraction session starts, based on time of day and what was
just opened.

- **Status:** not started
- **Blocked on:** #3
- **Notes:** the honest v1 is a threshold rule ("you have opened this app at
  this hour on 4 of the last 5 days"), not a prediction model

### 5. PDF / Excel report export
Formatted weekly and monthly reports.

- **Status:** not started — CSV export exists
  (`ui/processes_page.py:export_csv`) and works
- **Blocked on:** nothing
- **Notes:** adds dependencies (`reportlab` or `weasyprint`, `openpyxl`) —
  check their licences against the packaging decision in AUDIT BL-05 first

### 6. Team challenges & leaderboards
Shared goals across a group of linked users.

- **Status:** not started
- **Blocked on:** #1, and a real user account model — device IDs are not
  identities
- **Notes:** biggest scope of anything here, and the largest privacy surface.
  Needs its own consent step beyond the first-run gate, since it publishes one
  person's usage to others

### 7. Scheduled focus blocks
Time windows where limits tighten automatically — work hours, study sessions.

- **Status:** not started
- **Blocked on:** nothing
- **Notes:** not previously advertised. Probably the highest value-per-effort
  item on this list, and it works entirely locally

### 8. Priority support
A commitment, not a feature.

- **Notes:** only advertise once there is a support channel and a response
  target you can actually meet

---

## Before any of this ships

Premium cannot be sold at all until the monetization chain works. From
`AUDIT.md`:

- **SF-08** — mostly done. `core/licensing.py` holds the entitlement gate,
  signed and machine-bound, with a 14-day offline grace period; activation is a
  real flow. What remains is a `/license/verify` endpoint on the server and a
  merchant of record to sell keys
- **SF-09** — the sync API has no authentication
- **ST-05** — the backend is not in version control

Sequence: fix SF-08 and SF-09, commit the server, integrate a merchant of
record, *then* build features 1–7.

---

## Deliberately not doing

- **Ads.** The ad slot exists in `ui/app.py` but `_ADS` is empty and stays that
  way until a real ad network is integrated. Never fill it with real companies'
  names or taglines as placeholder content — that is false endorsement
  (AUDIT BL-01)
