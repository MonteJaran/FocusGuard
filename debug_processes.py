"""
debug_processes.py
Run this to see exactly what process names psutil detects on your system.
Compare these to what's stored in FocusGuard's database.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psutil
except ImportError:
    print("psutil is not installed! Run: pip install psutil")
    input("Press Enter to exit...")
    sys.exit(1)

from core.database import Database

print("=" * 60)
print("  FocusGuard - Process Diagnostic")
print("=" * 60)

# 1. What processes are currently running?
print("\n[1] All running process names (sorted):\n")
names = set()
paths = {}
for proc in psutil.process_iter(["name", "exe"]):
    try:
        n = proc.info.get("name") or ""
        e = proc.info.get("exe") or ""
        if n:
            names.add(n)
            paths[n.lower()] = e
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

for n in sorted(names, key=lambda x: x.lower()):
    print(f"  {n}")

# 2. What's stored in the DB?
print("\n" + "=" * 60)
print("[2] Apps stored in FocusGuard DB:\n")
try:
    db = Database()
    apps = db.get_all_tracked_apps()
    for app in apps:
        exe_name = app.get("exe_name") or "(none)"
        exe_path = app.get("exe_path") or "(none)"
        print(f"  {app['name']}")
        print(f"    exe_name: {exe_name}")
        print(f"    exe_path: {exe_path}")
        # Check if it would match
        en_lower = (app.get("exe_name") or "").lower().strip()
        ep_lower = (app.get("exe_path") or "").lower().replace("\\", "/").strip()
        running_names_lower = {n.lower() for n in names}
        match_name = en_lower and en_lower in running_names_lower
        match_path = ep_lower and any(ep_lower == p.lower().replace("\\", "/") for p in paths.values())
        if match_name or match_path:
            print("    STATUS: *** DETECTED AS RUNNING ***")
        else:
            print("    STATUS: not detected")
            if en_lower:
                # Find closest matches
                close = [n for n in names if en_lower.replace(".exe", "") in n.lower()]
                if close:
                    print(f"    Closest process matches: {close}")
        print()
    db.close()
except Exception as e:
    print(f"  Could not read DB: {e}")

print("=" * 60)
input("\nPress Enter to close...")
