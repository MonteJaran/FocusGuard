# FocusGuard

A Windows application usage tracker and limiter. Set daily limits on the apps
that distract you, see where your time actually goes, and have FocusGuard close
them when you go over.

All data stays on your PC unless you deliberately enable device sync.

## Running it

Run **`FocusGuard.bat`**. It checks for Python, installs dependencies, and
launches the app. You can set it to start automatically on boot from the
Settings tab.

On first run FocusGuard shows a privacy notice describing exactly what it
records. Nothing is monitored until you accept it.

> **Not ready for public release.** See [`AUDIT.md`](AUDIT.md) — there are open
> safety and legal items, and the launcher installs packages into your global
> Python at every start. Read it before distributing this to anyone.

## Layout

```
core/       monitoring, storage, config, consent gate, logging,
            protected-process denylist, staged app closing,
            usage-accounting rules, Win32 tray
ui/         Tkinter tabs (files, processes, insights, devices, settings)
server/     request/response models for the sync backend
tests/      pytest suite — see tests/README.md
```

## Development

```bash
python -m pip install pytest ruff
python -m pytest          # 216 tests, none touch your real data
python -m ruff check .    # lint
```

CI runs the suite on Linux and Windows against Python 3.10 and 3.12, plus lint,
a byte-compile of the Tk modules, and a real install of `requirements.txt`.

## Project documents

| File | What it is |
|---|---|
| [`AUDIT.md`](AUDIT.md) | Full readiness audit — legal, safety, and engineering findings with a phased plan |
| [`ROADMAP.md`](ROADMAP.md) | Planned features and what each one is blocked on |
| [`PRIVACY.md`](PRIVACY.md) | Privacy policy (draft — needs legal review) |

## Three rules for contributors

1. **Never advertise a feature that does not exist.** Anything unbuilt goes in
   `_PLANNED_FEATURES` and renders under a "Planned" heading. The build fails
   if this slips.
2. **Never put a real company's name in the ad slot.** `_ADS` stays empty until
   a real ad network is integrated. The build fails if this slips.
3. **Never close an app without warning it first.** Go through
   `core/procutil.close_app()`, which warns, posts `WM_CLOSE` so the app can
   save, and only terminates what refuses. Never call `psutil.kill()` directly,
   and never bypass `core/protected.py`.
