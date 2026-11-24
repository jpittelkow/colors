"""A plain API for Home Assistant (ADR 0020), with its own key.

Read: who is watching what, minutes used and left today, the inbox and failed downloads.
Act: the same parent actions as the Kids screen, and vacation mode.
The key is made in the parents' page (More > Home Assistant) and sent as `Authorization: Bearer <key>`.
"""
from __future__ import annotations

import hmac
import json
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import Database
from ..limits import clock
from .admin import require_admin

API = "/api/automation/v1"
NOW_PLAYING_FRESH_S = 60

router = APIRouter(prefix=API)
admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


def _db(request: Request) -> Database:
    return request.app.state.db


def require_key(request: Request) -> None:
    key = _db(request).get_setting("automation_key") or ""
    auth = request.headers.get("authorization", "")
    given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not key or not given or not hmac.compare_digest(given, key):
        raise HTTPException(401, "Missing or wrong automation key.")


def status(db: Database) -> dict:
    now = time.time()
    with db.conn() as c:
        out = []
        for p in c.execute("SELECT id, name, kind FROM profiles ORDER BY position, id").fetchall():
            ctx = clock.context(c, p["id"], now)
            dev = c.execute(
                "SELECT d.name AS tv, d.last_state, i.title FROM devices d JOIN items i ON i.id = d.last_item_id "
                "WHERE d.last_profile_id = ? AND d.last_heartbeat > ? AND d.revoked = 0 "
                "ORDER BY d.last_heartbeat DESC LIMIT 1",
                (p["id"], now - NOW_PLAYING_FRESH_S),
            ).fetchone()
            out.append({
                "id": p["id"],
                "name": p["name"],
                "watching": bool(dev and dev["last_state"] in ("playing", "starting")),
                "paused": bool(dev and dev["last_state"] == "paused"),
                "tv": dev["tv"] if dev else None,
                "title": dev["title"] if dev else None,
                "open": ctx.open,
                "reason": ctx.reason,
                "minutes_used_today": round(ctx.used_today_s / 60, 1),
                "minutes_left": None if ctx.left_s is None else round(max(0, ctx.left_s) / 60, 1),
                "last_one": ctx.lastone,
            })
        waiting = c.execute("SELECT count(*) FROM items WHERE approval = 'waiting'").fetchone()[0]
        failed = c.execute("SELECT count(*) FROM jobs WHERE state = 'failed'").fetchone()[0]
    return {
        "profiles": out,
        "anyone_watching": any(p["watching"] for p in out),
        "inbox_waiting": waiting,
        "downloads_failed": failed,
        "vacation_mode": db.get_setting("vacation_mode") == "1",
        "storage_full": db.get_setting("storage_full") == "1",
    }


@router.get("/status", dependencies=[Depends(require_key)])
def get_status(request: Request) -> dict:
    return status(_db(request))


class ActionIn(BaseModel):
    minutes: float = Field(default=0, ge=0, le=600)


def _act(db: Database, pids: list[int], action: str, minutes: float) -> None:
    with db.conn() as c:
        for pid in pids:
            try:
                clock.apply_action(c, pid, action, minutes)
            except ValueError:
                raise HTTPException(404, "Unknown action.")
            c.execute(
                "INSERT INTO events (ts, profile_id, type, data) VALUES (?, ?, 'parent', ?)",
                (time.time(), pid, json.dumps({"action": action, "minutes": minutes, "via": "home-assistant"})),
            )


@router.post("/profiles/{pid}/{action}", dependencies=[Depends(require_key)])
def profile_action(pid: int, action: str, request: Request, body: ActionIn | None = None) -> dict:
    db = _db(request)
    with db.conn() as c:
        if not c.execute("SELECT 1 FROM profiles WHERE id = ?", (pid,)).fetchone():
            raise HTTPException(404, "No such profile.")
    _act(db, [pid], action, (body or ActionIn()).minutes)
    return status(db)


@router.post("/all/{action}", dependencies=[Depends(require_key)])
def all_action(action: str, request: Request, body: ActionIn | None = None) -> dict:
    """The "everything off" button is POST /all/lock."""
    db = _db(request)
    with db.conn() as c:
        pids = [r[0] for r in c.execute("SELECT id FROM profiles")]
    _act(db, pids, action, (body or ActionIn()).minutes)
    return status(db)


class VacationIn(BaseModel):
    on: bool


@router.post("/vacation", dependencies=[Depends(require_key)])
def vacation(body: VacationIn, request: Request) -> dict:
    db = _db(request)
    db.set_setting("vacation_mode", "1" if body.on else "0")
    return status(db)


# ---- the key, managed from the parents' page ------------------------------------------------------------------------


@admin_router.get("/automation")
def key_get(request: Request) -> dict:
    db = _db(request)
    return {"key": db.get_setting("automation_key") or "", "vacation_mode": db.get_setting("vacation_mode") == "1"}


@admin_router.post("/automation/key")
def key_new(request: Request) -> dict:
    """Make a new key. The old one stops working."""
    key = secrets.token_urlsafe(24)
    _db(request).set_setting("automation_key", key)
    return {"key": key}


@admin_router.post("/automation/vacation")
def key_vacation(body: VacationIn, request: Request) -> dict:
    _db(request).set_setting("vacation_mode", "1" if body.on else "0")
    return {"vacation_mode": body.on}
