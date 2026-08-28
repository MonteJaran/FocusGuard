"""
consent.py - First-run privacy consent gate.

FocusGuard records which applications you run. Before it records anything, the
user has to be told what is collected and agree to it. This module owns that
decision and the record of it.

Two separate things are tracked, because they are two different questions:

  * local monitoring  - required for the app to do anything at all
  * device sync       - optional, and the only thing that sends data off the PC

Consent is versioned. Raising CONSENT_VERSION re-prompts every existing user,
which is what has to happen when the privacy policy changes materially.
"""

import os
import webbrowser
from datetime import datetime, timezone

# Bump when the privacy policy changes in a way that needs fresh consent.
CONSENT_VERSION = 1

# Published policy. Falls back to the bundled PRIVACY.md if unreachable.
PRIVACY_POLICY_URL = "https://focusguard.app/privacy"

_SUMMARY = (
    "FocusGuard records which applications you open and for how long, so it "
    "can show you your usage and enforce the limits you set.\n\n"
    "What it stores on this PC:\n"
    "    •  the apps you choose to track\n"
    "    •  when each one started and stopped\n"
    "    •  your settings and limits\n\n"
    "What it does NOT do:\n"
    "    •  no keystrokes, no screenshots, no window contents\n"
    "    •  no browsing history, no reading your files\n\n"
    "All of this stays on your computer. Nothing is uploaded unless you "
    "separately turn on device sync on the Devices tab."
)


def has_consented(config) -> bool:
    """True if the user has accepted the current version of the policy."""
    return int(config.get("consent_version", 0) or 0) >= CONSENT_VERSION


def record_consent(config, accepted: bool) -> None:
    """Persist the user's decision, with a timestamp and the policy version."""
    config.set("consent_version", CONSENT_VERSION if accepted else 0)
    config.set("consent_accepted", bool(accepted))
    config.set("consent_at", datetime.now(timezone.utc).isoformat() if accepted else "")


def revoke_consent(config) -> None:
    """Clear consent so the gate is shown again on next launch."""
    config.set("consent_version", 0)
    config.set("consent_accepted", False)
    config.set("consent_at", "")


def policy_path() -> str:
    """Absolute path to the PRIVACY.md shipped alongside the app."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "PRIVACY.md",
    )


def open_policy() -> None:
    """Open the published policy, falling back to the bundled copy."""
    try:
        webbrowser.open(PRIVACY_POLICY_URL)
    except Exception:
        local = policy_path()
        if os.path.isfile(local):
            try:
                webbrowser.open("file://" + local)
            except Exception:
                pass


def show_consent_dialog(parent) -> bool:
    """
    Show the blocking consent dialog.

    Returns True if the user ticked the box and accepted. The caller must exit
    the application on False - declining means we have no basis to record
    anything, so there is nothing for the app to do.
    """
    import tkinter as tk
    from tkinter import ttk

    BG, BG2, TEXT, TEXT2 = '#1a1a2e', '#16213e', '#e0e0e0', '#9090a0'
    ACCENT, MUTED = '#e94560', '#0f3460'

    dlg = tk.Toplevel(parent)
    dlg.title("FocusGuard — Before you start")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.transient(parent)

    result = {"accepted": False}

    tk.Label(dlg, text="Before you start",
             bg=BG, fg=TEXT, font=('Segoe UI', 15, 'bold')).pack(
        anchor='w', padx=24, pady=(22, 2))
    tk.Label(dlg, text="What FocusGuard records, and what it doesn't.",
             bg=BG, fg=TEXT2, font=('Segoe UI', 10)).pack(
        anchor='w', padx=24, pady=(0, 14))

    body = tk.Frame(dlg, bg=BG2)
    body.pack(fill='both', expand=True, padx=24)
    tk.Label(body, text=_SUMMARY, bg=BG2, fg=TEXT, justify='left',
             font=('Segoe UI', 10), wraplength=520).pack(
        anchor='w', padx=18, pady=16)

    link = tk.Label(dlg, text="Read the full privacy policy",
                    bg=BG, fg=ACCENT, cursor='hand2',
                    font=('Segoe UI', 10, 'underline'))
    link.pack(anchor='w', padx=24, pady=(12, 4))
    link.bind('<Button-1>', lambda _e: open_policy())

    agree_var = tk.BooleanVar(value=False)
    accept_btn = {}

    def _toggle(*_a):
        accept_btn['w'].config(state='normal' if agree_var.get() else 'disabled')

    chk = ttk.Checkbutton(
        dlg,
        text="I have read and agree to the privacy policy",
        variable=agree_var,
        command=_toggle,
    )
    chk.pack(anchor='w', padx=22, pady=(6, 4))

    tk.Label(dlg,
             text="Nothing is recorded until you agree. Declining closes the app.",
             bg=BG, fg=TEXT2, font=('Segoe UI', 9)).pack(
        anchor='w', padx=24, pady=(0, 14))

    btns = tk.Frame(dlg, bg=BG)
    btns.pack(fill='x', padx=24, pady=(0, 20))

    def _accept():
        result["accepted"] = True
        dlg.destroy()

    def _decline():
        result["accepted"] = False
        dlg.destroy()

    accept_btn['w'] = tk.Button(
        btns, text="Agree and continue",
        bg=ACCENT, fg='#ffffff', font=('Segoe UI', 10, 'bold'),
        relief='flat', bd=0, padx=18, pady=9, cursor='hand2',
        state='disabled', command=_accept,
    )
    accept_btn['w'].pack(side='right')

    tk.Button(btns, text="Decline and exit",
              bg=MUTED, fg=TEXT, font=('Segoe UI', 10),
              relief='flat', bd=0, padx=14, pady=9, cursor='hand2',
              command=_decline).pack(side='right', padx=(0, 10))

    # Closing the window is a decline, not an accept.
    dlg.protocol("WM_DELETE_WINDOW", _decline)

    # Centre on the parent when it is on screen, otherwise on the display —
    # at first run the main window is still hidden behind this gate.
    dlg.update_idletasks()
    w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    if parent.winfo_viewable() and parent.winfo_width() > 1:
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    else:
        x = (dlg.winfo_screenwidth() - w) // 2
        y = (dlg.winfo_screenheight() - h) // 3
    dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

    dlg.grab_set()
    dlg.focus_force()
    parent.wait_window(dlg)

    return result["accepted"]
