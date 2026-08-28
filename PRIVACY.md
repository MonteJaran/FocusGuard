# FocusGuard Privacy Policy

**Last updated:** 2026-08-26
**Applies to:** FocusGuard for Windows, version 1.0.0

> **Draft — needs legal review before public release.** This document describes
> what the code actually does today, verified against the source. It is written
> to be accurate, not to be legally sufficient in every jurisdiction. Have a
> qualified lawyer review it before you ship to the public or take money.
> See `AUDIT.md` (BL-03) for the surrounding requirements.

---

## The short version

FocusGuard runs on your computer and records which applications you open and
for how long. **By default, all of that stays on your PC.** Nothing is uploaded
anywhere unless you deliberately turn on device sync.

---

## What FocusGuard records on your computer

To do its job — showing you your usage and enforcing the limits you set —
FocusGuard stores locally:

| Data | Where | Why |
|---|---|---|
| Names and file paths of the apps you choose to track | `%LOCALAPPDATA%\FocusGuard\focusguard.db` | So it can recognise them when they run |
| Start time, end time and duration of each session | same database | To calculate your usage against your limits |
| Your settings and limits | `%LOCALAPPDATA%\FocusGuard\config.json` | To remember your preferences |
| A diagnostic log | `%LOCALAPPDATA%\FocusGuard\focusguard.log` | To help diagnose problems |

FocusGuard checks the list of running processes to detect the apps you asked it
to track. It does **not** record what you type, what you look at, the contents
of any window, your browsing history, your files, or screenshots.

This data is not encrypted at rest. Anyone with access to your Windows user
account can read it.

## What leaves your computer

**Nothing, unless you enable device sync.**

Device sync is off until you go to the Devices tab and register the device. If
you do, the following is sent to our server:

- **Your computer's hostname** — used to label the device in your own device
  list. Hostnames often contain a person's name.
- **An email address, only if you type one** — the field is optional. If you
  leave it blank, no email is sent.
- **Usage totals** — for each app you track, the app's name, category and
  seconds used, uploaded roughly every 30 minutes.

The server is operated on Google Cloud (Firebase Cloud Functions) in the United
States. If you are in the EU or UK, this means your data is transferred outside
your region.

We do **not** sell your data, share it with advertisers, or use it to build
advertising profiles.

## Checking for updates

On startup FocusGuard fetches a small file from our server to see whether a
newer version exists. That request unavoidably reveals your IP address and the
version you are running, the same as visiting any web page. It sends nothing
about you, your apps or your usage, and it never downloads or installs anything
— if there is an update, you are told, and you choose whether to get it.

Turn it off in Settings if you would rather it did not happen.

## Legal basis (EU/UK users)

Local-only use involves no transfer to us. Where you enable sync, we rely on
your **consent**, given through the setup screen when you first run the app and
again when you register a device. You may withdraw it at any time by not
registering, or by deleting your data as described below.

## How long we keep it

By default, usage history older than **one year** is deleted automatically. You
can change that in Settings, including keeping everything forever.

Your tracked-app list and settings stay until you remove them. Synced data is
retained until you request deletion.

## Your choices

- **Use FocusGuard entirely offline.** Never register a device and nothing is
  ever transmitted.
- **See your data.** It is a standard SQLite database at the path above. The
  Export CSV button on the Processes tab produces a readable copy.
- **Delete your data.** Settings → Delete All Data removes your usage history,
  your tracked-app list, your settings and the diagnostic log from this PC.

> **Note:** that button covers this computer only. If you registered the device
> for sync, data already uploaded to the server is not covered — there is no
> server-side deletion endpoint yet. This is tracked as BL-06 in `AUDIT.md`.

## Children

FocusGuard is not intended for children under 16. Do not register a device or
enter an email address if you are under 16.

## Monitoring other people

FocusGuard is intended for monitoring your own device. Installing it on someone
else's computer to record their activity without telling them may be illegal
where you live. That is your responsibility, not ours.

## Changes

Material changes will be shown in the app and require consent again before any
new data is collected.

## Contact

Add a real contact address here before release. A privacy policy with no way to
reach the operator does not satisfy GDPR Article 13.
