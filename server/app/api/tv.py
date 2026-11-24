"""The TV app's API (ADR 0017). The server sends finished screens; the app draws them.

Rule for this file, checked by tests/test_guards.py: every route that returns items or a stream gets them from
`pipeline` (ADR 0022). Nothing here reads the items table directly for a child.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..ai import picks
from .. import channel_pics
from .extras import avatar_url
from ..db import Database
from ..limits import clock
from ..rules import pipeline
from ..security import new_pair_code, new_token, token_hash
from ..sources import plex

API = "/api/tv/v1"
WATCHED_AT = 0.9  # share of the length after which a video counts as watched
HEARTBEAT_FRESH_S = 90
STARTED_MAY_FINISH = ("open", "fits")  # a video that already started may finish (ADR 0012)

router = APIRouter(prefix=API)


def _db(request: Request) -> Database:
    return request.app.state.db


# ---- pairing (ADR 0018) --------------------------------------------------------------------------------------------


@router.post("/pair/start")
def pair_start(request: Request) -> dict:
    """A new TV asks for a code to show. It keeps the token; the token works once a parent types the code."""
    token, code = new_token(), new_pair_code()
    with _db(request).conn() as c:
        c.execute("DELETE FROM devices WHERE paired_at IS NULL AND created_at < ?", (time.time() - 3600,))
        c.execute(
            "INSERT INTO devices (token_hash, pair_code, created_at) VALUES (?, ?, ?)",
            (token_hash(token), code, time.time()),
        )
    return {"token": token, "code": code}


def _device_row(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "No device token.")
    with _db(request).conn() as c:
        row = c.execute("SELECT * FROM devices WHERE token_hash = ?", (token_hash(auth[7:].strip()),)).fetchone()
    if not row or row["revoked"]:
        raise HTTPException(401, "Unknown or revoked TV.")
    return row


@router.get("/pair/status")
def pair_status(request: Request) -> dict:
    row = _device_row(request)
    return {"paired": row["paired_at"] is not None, "name": row["name"]}


def device(request: Request) -> int:
    """Dependency: the id of a paired, unrevoked TV."""
    row = _device_row(request)
    if row["paired_at"] is None:
        raise HTTPException(403, "This TV is not paired yet.")
    with _db(request).conn() as c:
        c.execute("UPDATE devices SET last_seen = ? WHERE id = ?", (time.time(), row["id"]))
    return row["id"]


# ---- screens -------------------------------------------------------------------------------------------------------


def _card(row, profile_id: int) -> dict:
    """One video card. Only what the app needs to draw it and ask to play it."""
    return {
        "id": row["id"],
        "title": row["title"],
        "kind": row["kind"],
        "container_id": row["container_id"],
        "container_title": row["container_title"],
        "duration_s": row["duration_s"],
        "remaining_s": row["remaining_s"],
        "position_s": row["position_s"],
        "watched": bool(row["watched"]),
        "thumb": f"{API}/thumb/{row['id']}?profile_id={profile_id}",
    }


PROFILE_COLUMNS = "id, name, kind, avatar, avatar_color"


def _profile_out(row) -> dict:
    d = dict(row)
    d["avatar_url"] = avatar_url(d["avatar"])  # ADR 0036
    return d


def _profile(c, profile_id: int):
    row = c.execute(f"SELECT {PROFILE_COLUMNS} FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        raise HTTPException(404, "No such profile.")
    return row


@router.get("/profiles")
def profiles(request: Request, device_id: int = Depends(device)) -> list[dict]:
    with _db(request).conn() as c:
        return [_profile_out(r) for r in c.execute(f"SELECT {PROFILE_COLUMNS} FROM profiles ORDER BY position, id")]


@router.get("/home")
def home(profile_id: int, request: Request, device_id: int = Depends(device)) -> dict:
    """The home screen as ordered rows (ADR 0013), already filtered by limits and time-fit (ADR 0012)."""
    with _db(request).conn() as c:
        profile = _profile(c, profile_id)
        ctx = clock.context(c, profile_id)
        everything = pipeline.visible_items(c, profile_id, ctx=ctx, order="new", limit=500)
        # Only ever a reordering of `everything`, which already passed every step (ADR 0034).
        picked = picks.row(c, _db(request), profile_id, everything)
    if ctx.lastone_item is not None:
        # The last one is chosen: it is the only thing left to watch.
        last = _only_lastone(ctx, everything)
        rows = [{"id": "lastone", "title": "Your last one", "cards": [_card(r, profile_id) for r in last]}] if last else []
        return {"profile": _profile_out(profile), "time": ctx.public(), "last_pick": False, "rows": rows}
    rows = []
    resume = [r for r in everything if r["position_s"] > 0 and not r["watched"]]
    if resume:
        rows.append({"id": "continue", "title": "Continue watching", "cards": [_card(r, profile_id) for r in resume[:20]]})
    if picked:
        rows.append({"id": "picked", "title": "Picked for you", "cards": [_card(r, profile_id) for r in picked]})
    if everything:
        rows.append({"id": "new", "title": "New", "cards": [_card(r, profile_id) for r in everything[:20]]})
    by_container: dict[int, list] = {}
    for r in everything:
        by_container.setdefault(r["container_id"], []).append(r)
    for cid, items in sorted(by_container.items(), key=lambda kv: kv[1][0]["container_title"].lower()):
        rows.append(
            {
                "id": f"container-{cid}",
                "title": items[0]["container_title"],
                "container_id": cid,
                "cards": [_card(r, profile_id) for r in items[:30]],
            }
        )
    # Few videos still fit: offer "one more" instead of a near-empty home (ADR 0012).
    last_pick = ctx.limited and ctx.open and 0 < len(everything) <= 3
    return {"profile": _profile_out(profile), "time": ctx.public(), "last_pick": last_pick, "rows": rows}


@router.get("/container/{container_id}")
def container(container_id: int, profile_id: int, request: Request, device_id: int = Depends(device)) -> dict:
    with _db(request).conn() as c:
        _profile(c, profile_id)
        items = _only_lastone(clock.context(c, profile_id),
                              pipeline.visible_items(c, profile_id, container_id=container_id, order="upload"))
    if not items:
        raise HTTPException(404, "Nothing to show here.")
    return {"id": container_id, "title": items[0]["container_title"], "cards": [_card(r, profile_id) for r in items]}


# ---- the menu: Channels, Recently watched, Recommended, New ---------------------------------------------------------

SHELVES = {"recent": "Recently watched", "picked": "Recommended", "new": "New"}


@router.get("/channels")
def channels(profile_id: int, request: Request, device_id: int = Depends(device)) -> dict:
    """Every channel with something this profile may watch now, newest first, with its picture."""
    with _db(request).conn() as c:
        _profile(c, profile_id)
        ctx = clock.context(c, profile_id)
        items = _only_lastone(ctx, pipeline.visible_items(c, profile_id, ctx=ctx, order="new", limit=2000))
        ext = {r["id"]: r["external_id"] for r in c.execute("SELECT id, external_id FROM containers")}
    pics = request.app.state.pics
    by: dict[int, list] = {}
    for r in items:
        by.setdefault(r["container_id"], []).append(r)
    out = []
    for cid, rows in by.items():
        has_pic = channel_pics.valid(ext.get(cid, "")) and pics.file(ext[cid]) is not None
        out.append({
            "id": cid, "title": rows[0]["container_title"], "count": len(rows),
            "unwatched": sum(1 for r in rows if not r["watched"]),
            # The channel's own picture when there is one, else its newest video's.
            "picture": f"{API}/channel-picture/{cid}?profile_id={profile_id}" if has_pic else f"{API}/thumb/{rows[0]['id']}?profile_id={profile_id}",
            "round": has_pic,
        })
    return {"channels": out}


@router.get("/channel-picture/{container_id}")
def channel_picture(container_id: int, profile_id: int, request: Request, device_id: int = Depends(device)):
    with _db(request).conn() as c:
        # Only a channel this profile can see something in right now (ADR 0022).
        if not pipeline.visible_items(c, profile_id, container_id=container_id, limit=1, skip=STARTED_MAY_FINISH):
            raise HTTPException(404)
        row = c.execute("SELECT external_id FROM containers WHERE id = ?", (container_id,)).fetchone()
    f = request.app.state.pics.file(row["external_id"]) if row and channel_pics.valid(row["external_id"]) else None
    if not f:
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/shelf/{kind}")
def shelf(kind: str, profile_id: int, request: Request, device_id: int = Depends(device)) -> dict:
    """One whole list from the menu, as a grid. Same filtering as the home rows (ADR 0012, ADR 0034)."""
    if kind not in SHELVES:
        raise HTTPException(404, "No such list.")
    with _db(request).conn() as c:
        _profile(c, profile_id)
        ctx = clock.context(c, profile_id)
        if kind == "recent":
            seen = [r[0] for r in c.execute(
                "SELECT item_id FROM watch_state WHERE profile_id = ? ORDER BY updated_at DESC LIMIT 120", (profile_id,))]
            rank = {item_id: i for i, item_id in enumerate(seen)}
            rows = sorted(pipeline.visible_items(c, profile_id, ctx=ctx, item_ids=seen, limit=120), key=lambda r: rank[r["id"]])
        else:
            everything = pipeline.visible_items(c, profile_id, ctx=ctx, order="new", limit=500)
            if kind == "new":
                rows = everything[:120]
            else:
                rows = picks.row(c, _db(request), profile_id, everything) or _liked_channels_first(c, profile_id, everything)
    return {"id": 0, "title": SHELVES[kind], "cards": [_card(r, profile_id) for r in _only_lastone(ctx, rows)]}


def _only_lastone(ctx: clock.Context, rows: list) -> list:
    """Once the last one is chosen, every list shows only that video."""
    return rows if ctx.lastone_item is None else [r for r in rows if r["id"] == ctx.lastone_item]


def _liked_channels_first(c, profile_id: int, everything: list) -> list:
    """Recommended without AI picks: unwatched videos, from the channels this child watches most first."""
    plays = {r[0]: r[1] for r in c.execute(
        "SELECT i.container_id, count(*) FROM watch_state w JOIN items i ON i.id = w.item_id "
        "WHERE w.profile_id = ? GROUP BY i.container_id", (profile_id,))}
    fresh = [r for r in everything if not r["watched"] and r["position_s"] == 0]
    return sorted(fresh, key=lambda r: -plays.get(r["container_id"], 0))[:60]  # stable: newest first within a channel


@router.get("/upnext")
def upnext(profile_id: int, item_id: int, request: Request, device_id: int = Depends(device)) -> dict:
    """What to offer after a video: same channel first, then anything new, unwatched first, all of it fitting."""
    with _db(request).conn() as c:
        ctx = clock.context(c, profile_id)
        items = pipeline.visible_items(c, profile_id, ctx=ctx, order="new", limit=200)
    if ctx.lastone:
        return {"autoplay_n": 0, "cards": []}  # nothing comes after the last one
    current = next((r for r in items if r["id"] == item_id), None)
    rest = [r for r in items if r["id"] != item_id]
    same = [r for r in rest if current and r["container_id"] == current["container_id"]]
    ordered = sorted(same, key=lambda r: r["watched"]) + sorted(
        [r for r in rest if r not in same], key=lambda r: r["watched"]
    )
    return {"autoplay_n": ctx.autoplay_n, "cards": [_card(r, profile_id) for r in ordered[:6]]}


@router.get("/thumb/{item_id}")
def thumb(item_id: int, profile_id: int, request: Request, device_id: int = Depends(device)):
    with _db(request).conn() as c:
        if not pipeline.can_play(c, profile_id, item_id, skip=STARTED_MAY_FINISH):
            raise HTTPException(404)
        row = c.execute("SELECT source, thumb_path, external_id FROM items WHERE id = ?", (item_id,)).fetchone()
    if row["source"] == "plex":
        return plex.thumb(request.app.state, row["external_id"])
    if not row["thumb_path"]:
        raise HTTPException(404)
    return FileResponse(
        request.app.state.cfg.library_dir / row["thumb_path"], headers={"Cache-Control": "private, max-age=86400"}
    )


# ---- playback ------------------------------------------------------------------------------------------------------


class PlayIn(BaseModel):
    profile_id: int
    item_id: int


@router.post("/play")
def play(body: PlayIn, request: Request, device_id: int = Depends(device)) -> dict:
    """Every rule is checked again here, at the moment of playing (ADR 0017)."""
    with _db(request).conn() as c:
        ctx = clock.context(c, body.profile_id)
        found = pipeline.visible_items(c, body.profile_id, ctx=ctx, item_ids=[body.item_id], limit=1)
        if not found:
            if not ctx.open:
                raise HTTPException(403, {"reason": "closed", "message": ctx.reason, "time": ctx.public()})
            raise HTTPException(403, {"reason": "not_available", "message": "This video is not available."})
        item = found[0]
        # "Last one" allows one video: the first one started, or the one already playing (ADR 0011).
        if ctx.lastone and not (
            ctx.lastone_item == body.item_id
            or (ctx.lastone_item is None and clock.claim_lastone(c, body.profile_id, body.item_id))
        ):
            raise HTTPException(403, {"reason": "lastone", "message": "That was the last one.", "time": ctx.public()})
        segments = [
            {"start_s": r["start_s"], "end_s": r["end_s"], "category": r["category"]}
            for r in c.execute(
                "SELECT start_s, end_s, category FROM segments WHERE item_id = ? ORDER BY start_s", (body.item_id,)
            )
        ]
        now = time.time()
        c.execute(
            "INSERT INTO events (ts, profile_id, device_id, item_id, type) VALUES (?, ?, ?, ?, 'started')",
            (now, body.profile_id, device_id, body.item_id),
        )
        c.execute(
            "UPDATE devices SET last_item_id = ?, last_heartbeat = ?, last_profile_id = ?, last_state = 'starting', "
            "last_position_s = ?, fit_left_s = ? WHERE id = ?",
            (body.item_id, now, body.profile_id, item["position_s"], ctx.left_s, device_id),
        )
    # Valid for the video's length plus a margin; the heartbeat keeps it alive beyond that (ADR 0006).
    token = request.app.state.signer.sign(
        {"i": body.item_id, "d": device_id, "p": body.profile_id}, ttl_s=item["duration_s"] + 3600
    )
    resume = 0 if item["watched"] else item["position_s"]
    return {
        "item": _card(item, body.profile_id),
        "stream_url": f"{API}/stream/{token}",
        "resume_s": resume,
        "skip_segments": segments,
        "heartbeat_s": 15,
        "time": ctx.public(),
    }


class HeartbeatIn(BaseModel):
    profile_id: int
    item_id: int
    position_s: float = Field(ge=0)
    state: str = Field(default="playing", pattern="^(playing|paused|ended)$")


@router.post("/heartbeat")
def heartbeat(body: HeartbeatIn, request: Request, device_id: int = Depends(device)) -> dict:
    """Counts watched time, saves the resume point, and tells the app when to stop (ADR 0011, 0012)."""
    now = time.time()
    with _db(request).conn() as c:
        dev = c.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        # Only the video this TV started with /play may run past the limits (ADR 0012); any other item must pass
        # every step. Hidden or unassigned while it plays: stop at the next heartbeat (ADR 0009).
        started = dev["last_item_id"] == body.item_id and dev["last_profile_id"] == body.profile_id
        found = pipeline.visible_items(
            c, body.profile_id, item_ids=[body.item_id], limit=1, skip=STARTED_MAY_FINISH if started else ()
        )
        if not found:
            return {"command": "stop", "reason": "not_available"}
        clock.count_heartbeat(c, dev, body.profile_id, body.state, now)

        duration = found[0]["duration_s"]
        watched = body.state == "ended" or (duration > 0 and body.position_s >= duration * WATCHED_AT)
        was_watched = bool(found[0]["watched"])
        c.execute(
            "INSERT INTO watch_state (profile_id, item_id, position_s, watched, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (profile_id, item_id) DO UPDATE SET position_s = excluded.position_s, "
            "watched = max(watched, excluded.watched), updated_at = excluded.updated_at",
            (body.profile_id, body.item_id, 0 if body.state == "ended" else body.position_s, int(watched), now),
        )
        if watched and not was_watched:
            c.execute(
                "INSERT INTO events (ts, profile_id, device_id, item_id, type) VALUES (?, ?, ?, ?, 'finished')",
                (now, body.profile_id, device_id, body.item_id),
            )
        c.execute(
            "UPDATE devices SET last_item_id = ?, last_heartbeat = ?, last_profile_id = ?, last_state = ?, "
            "last_position_s = ? WHERE id = ?",
            (body.item_id, now, body.profile_id, body.state, body.position_s, device_id),
        )

        ctx = clock.context(c, body.profile_id, now)
        command, reason = None, ""
        if ctx.hard_stop:
            command, reason = "stop", "parent"
        elif not ctx.open:
            if body.state == "ended":
                command, reason = "timeup", ctx.reason
            elif ctx.over_s > clock.HARD_CAP_S:
                command, reason = "timeup", ctx.reason
        elif ctx.lastone_item is not None and ctx.lastone_item != body.item_id:
            command, reason = "timeup", "Last one"  # still playing something else: the last one is another video
        elif ctx.lastone and body.state == "ended":
            clock.clear_today(c, body.profile_id, ("lastone",), now)
            clock.add_override(c, body.profile_id, "lock", now=now, note="Last one finished")
            command, reason = "timeup", "Last one finished"
    return {"command": command, "reason": reason, "time": ctx.public()}


@router.get("/stream/{token}")
def stream(token: str, request: Request):
    """Serve the file for a signed token. The player sends range requests; FileResponse answers them."""
    claims = request.app.state.signer.read(token, allow_expired=True)
    if not claims:
        raise HTTPException(403, "Bad stream token.")
    with _db(request).conn() as c:
        dev = c.execute(
            "SELECT revoked, last_item_id, last_profile_id, last_heartbeat FROM devices WHERE id = ?", (claims["d"],)
        ).fetchone()
        if not dev or dev["revoked"]:
            raise HTTPException(403, "Unknown or revoked TV.")
        if claims["expired"]:
            fresh = dev["last_item_id"] == claims["i"] and (dev["last_heartbeat"] or 0) > time.time() - HEARTBEAT_FRESH_S
            if not fresh:
                raise HTTPException(403, "Stream token expired.")
        # Limits stop a running video through the heartbeat (ADR 0012), but the stream itself is cut once a parent
        # ended it or the hard cap has passed, so a client that ignores the heartbeat can't keep watching.
        ctx = clock.context(c, claims["p"])
        if ctx.hard_stop or (not ctx.open and ctx.over_s > clock.HARD_CAP_S):
            raise HTTPException(403, "Time is up.")
        if ctx.lastone_item is not None and ctx.lastone_item != claims["i"]:
            raise HTTPException(403, "That was the last one.")  # an older token for another video
        # Only the video this TV last started for this profile may run past the limits, and once over the limit
        # only while the TV keeps sending heartbeats (watched time is counted from them).
        started = dev["last_item_id"] == claims["i"] and dev["last_profile_id"] == claims["p"]
        beating = (dev["last_heartbeat"] or 0) > time.time() - HEARTBEAT_FRESH_S
        if not ctx.open and not (started and beating):
            raise HTTPException(403, "Time is up.")
        if not pipeline.can_play(c, claims["p"], claims["i"], ctx=ctx, skip=STARTED_MAY_FINISH if started else ()):
            raise HTTPException(403, "This video is not available.")
        row = c.execute("SELECT source, file_path, media_key FROM items WHERE id = ?", (claims["i"],)).fetchone()
    if row["source"] == "plex":
        return plex.stream(request, row["media_key"])
    path = request.app.state.cfg.library_dir / row["file_path"]
    if not path.is_file():
        raise HTTPException(404, "The file is missing from the library.")
    return FileResponse(path, media_type="video/mp4")
