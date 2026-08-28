# Building and distributing FocusGuard

> **Nothing here has been tested on Windows yet.** These files were written
> against the PyInstaller and Inno Setup documentation but never run — the
> first real build will need adjustment. Treat the smoke test in `build.ps1`
> as the gate, not this document.

## Requirements

| Tool | Why | Where |
|---|---|---|
| Python 3.10+ | Building | python.org |
| PyInstaller | Freezes the app | `pip install pyinstaller` |
| Inno Setup 6 | Builds the installer | https://jrsoftware.org/isdl.php |
| `signtool.exe` | Signing | Windows SDK |

## Building

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The script runs the tests and the linter first and refuses to build from a red
tree. Then it generates the Windows version resource from `core/version.py`,
runs PyInstaller, **launches the result and checks it stays running for eight
seconds**, and finally builds the installer.

That smoke test matters more than it looks. A frozen build that is missing a
hidden import fails at launch, and because this is a GUI app it fails
*silently* — no console, no error, just nothing. Without the check you find out
from a user.

Output:

```
dist/FocusGuard/            the folder build
dist/installer/FocusGuard-<version>-setup.exe
```

## Why a folder build, not one-file

One-file unpacks the entire app to `%TEMP%` on every launch. It is slower, and
"executable unpacks itself to temp and runs from there" is a behaviour
antivirus scores badly — this app already enumerates and closes processes, so
it does not need more suspicion. A folder build also keeps every DLL separately
signable; signing a one-file stub leaves its payload unsigned.

The user still downloads exactly one file, because Inno Setup wraps the folder.

## Code signing

**Unsigned, SmartScreen shows a full-screen "Windows protected your PC" warning
and most people cancel.** For an app that reads your process list, that warning
is fatal to installs.

```powershell
$env:FOCUSGUARD_CERT_THUMBPRINT = "<thumbprint>"
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Sign
```

The build signs the executable *before* packaging and the installer after, so
both are covered.

### Getting a certificate

| Option | Cost | Notes |
|---|---|---|
| **Azure Trusted Signing** | ~$10/month | Cheapest real option. Needs a verified identity. |
| OV certificate | €200–400/yr | Signs immediately, but reputation builds slowly — early users still see warnings. |
| EV certificate | €300–600/yr | Instant SmartScreen reputation. Requires a hardware token. |
| **Microsoft Store** | Very low, possibly free | See below. |

### The Microsoft Store route

Publishing through the Store means **Microsoft signs the package**, so
SmartScreen does not warn at all — the same outcome as a certificate, for a
fraction of the cost. The individual developer account has historically been a
one-time fee of about $19; Microsoft has changed this more than once, so check
the current terms.

It also gives you a distribution channel and a built-in payment system, which
matters because FocusGuard has no payment path of its own yet (AUDIT SF-08).

For a pre-traction app this is almost certainly the right first move. The
tradeoff is Store certification review and less control over the listing.

## Antivirus

Even signed, expect some engines to flag early builds. FocusGuard enumerates
processes, terminates processes, and registers a startup entry — individually
normal, together a generic-trojan shape.

Before any public release:

1. Sign everything.
2. Submit to Microsoft at https://www.microsoft.com/wdsi/filesubmission
3. Submit false positives to the other major vendors.
4. Say plainly in your listing *why* the app needs process access.

`core/protected.py` matters here too: an app that terminates Task Manager on a
loop is not a false positive to a heuristic engine, it is a correct detection.
Do not weaken that denylist.

## Release checklist

- [ ] Bump `__version__` in `core/version.py` (a test asserts `pyproject.toml` agrees)
- [ ] `python -m pytest` and `python -m ruff check .` — both clean
- [ ] Build, and confirm the smoke test passes
- [ ] Install on a **clean Windows VM**, not your dev machine — that is the only way install-path bugs surface (it is how AUDIT SF-03 hid: `create_shortcut.ps1` used PowerShell 7 syntax and failed for every user on stock Windows)
- [ ] Confirm the first-run privacy gate appears and declining exits
- [ ] Confirm the tray icon appears and Quit works — `core/tray.py` is Win32 ctypes and **has never been run**
- [ ] Confirm Settings → Delete All Data removes the database, config and logs
- [ ] Uninstall, and confirm the Run key and `%LOCALAPPDATA%\FocusGuard` are handled
- [ ] Confirm an app is warned before it is closed, and gets a chance to save

## Publishing an update

`core/updates.py` checks a static JSON manifest at startup and tells the user
if a newer version exists. It never downloads or installs anything — an app
that can silently replace its own executable is a much larger security surface
than this project needs.

The manifest is a static file, so host it free on GitHub Pages, Cloudflare
Pages, or anywhere. See `packaging/version.json.example`:

```json
{
  "version": "1.1.0",
  "url": "https://focusguard.app/download",
  "notes": "Fixes a crash when...",
  "critical": false
}
```

Set `critical: true` for a security fix — the app then interrupts rather than
showing a dismissible bar. Point `UPDATE_MANIFEST_URL` in `core/updates.py` at
wherever you host it, and publish the new manifest **after** the download is
actually live.

## Still missing

- **Dependencies are not pinned by hash.** `requirements.txt` uses lower bounds,
  so two builds a month apart are not identical. Pin exactly before release.
