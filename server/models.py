"""
models.py — Minimal Pydantic request/response models.

Key design: single-char JSON keys to shrink every payload.
Upload cycle: every 30 minutes.
"""

from pydantic import BaseModel


# ── Registration ───────────────────────────────────────────────────────────────

class RegisterReq(BaseModel):
    e: str | None = None   # email — discarded immediately after response

class RegisterResp(BaseModel):
    id: str                   # 24-char device_id


# ── App list sync (sent once, or when tracked apps change) ────────────────────
# Each entry: [local_db_id, name, category]
# Example: [[1,"Discord","Social"],[2,"VS Code","Development"]]

class AppSyncReq(BaseModel):
    d: str                    # device_id
    a: list[list]             # [[local_id, name, category], ...]

class AppSyncResp(BaseModel):
    m: dict                   # {"local_id": server_id, ...}


# ── 30-minute usage upload ────────────────────────────────────────────────────
# "a" contains only apps that had usage > 0 in this window.
# Each entry: [server_app_id, seconds_used]
# Example: [[42,1800],[43,270]]

class UploadReq(BaseModel):
    d: str                    # device_id
    t: int                    # period end — unix timestamp (int, not ISO string)
    a: list[list]             # [[server_app_id, seconds], ...]  only s>0

class UploadResp(BaseModel):
    ok: int = 1


# ── Cross-device sync response ────────────────────────────────────────────────

class SyncResp(BaseModel):
    apps: dict                # {server_app_id: total_sec_today}
    devices: int              # number of linked devices


# ── Device linking ────────────────────────────────────────────────────────────

class LinkNewResp(BaseModel):
    k: str                    # 8-char key, valid 5 minutes

class LinkJoinReq(BaseModel):
    d: str                    # joining device_id
    k: str                    # key from the host device

class LinkJoinResp(BaseModel):
    ok: int = 1
    grp: str                  # shared group id


# ── Global anonymous stats ────────────────────────────────────────────────────

class GlobalStatsResp(BaseModel):
    # {category: {sec_today, users_today}}
    cats: dict
    total_users: int
