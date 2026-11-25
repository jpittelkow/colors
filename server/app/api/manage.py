"""More of the parents' API: channels and subscriptions, video details, limits and the kids, Plex, settings,
reports. Everything here sits behind the admin password (ADR 0018)."""
from __future__ import annotations

import json
import logging
import re
import shutil
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..curation import blocklist, unwatched
from ..db import Database
from ..downloads import jobs, loudness, subscriptions
from ..limits import clock
from ..rules import pipeline
from ..sources import plex
from .admin import require_admin
from .extras import avatar_url

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
log = logging.getLogger("kidtube.manage")

NOW_PLAYING_FRESH_S = 60


def _db(request: Request) -> Database:
    return request.app.state.db


def _ids(s: str | None) -> list[int]:
    return sorted({int(x) for x in (s or "").split(",") if x})


# ---- channels and subscriptions ------------------------------------------------------------------------------------


@router.get("/channels")
def channels(request: Request) -> list[dict]:
    with _db(request).conn() as c:
        rows = c.execute(
            "SELECT c.id, c.source, c.kind, c.external_id, c.title, c.url, c.thumb_url, c.trusted, c.rested_until, "
            "(SELECT count(*) FROM items i WHERE i.container_id = c.id AND i.status = 'ready') AS ready, "
            "(SELECT count(*) FROM items i WHERE i.container_id = c.id AND i.approval = 'waiting' "
            " AND i.status <> 'failed') AS waiting, "
            "(SELECT count(*) FROM items i WHERE i.container_id = c.id AND i.approval = 'approved') AS approved, "
            "(SELECT group_concat(a.profile_id) FROM assignments a WHERE a.container_id = c.id OR a.item_id IN "
            " (SELECT i.id FROM items i WHERE i.container_id = c.id AND i.approval = 'approved')) AS seen_by, "
            "(SELECT max(added_at) FROM items i WHERE i.container_id = c.id) AS newest, "
            "(SELECT group_concat(a.profile_id) FROM assignments a WHERE a.container_id = c.id) AS profile_ids, "
            "s.id AS sub_id, s.mode AS sub_mode, s.active AS sub_active "
            "FROM containers c LEFT JOIN subscriptions s ON s.container_id = c.id "
            "ORDER BY newest DESC NULLS LAST, c.title COLLATE NOCASE"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["profile_ids"] = _ids(d["profile_ids"])
        d["seen_by"] = _ids(d["seen_by"])
        out.append(d)
    return out


@router.get("/channels/{cid}")
def channel(cid: int, request: Request) -> dict:
    with _db(request).conn() as c:
        row = c.execute("SELECT * FROM containers WHERE id = ?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "No such channel.")
        sub = c.execute("SELECT * FROM subscriptions WHERE container_id = ?", (cid,)).fetchone()
        profile_ids = [r[0] for r in c.execute("SELECT profile_id FROM assignments WHERE container_id = ?", (cid,))]
        items = [
            dict(r)
            for r in c.execute(
                "SELECT id, title, duration_s, upload_date, status, approval, blocked_reason, play_note, thumb_url, "
                "thumb_path, source, external_id FROM items WHERE container_id = ? "
                "ORDER BY upload_date DESC, added_at DESC LIMIT 300",
                (cid,),
            )
        ]
    for it in items:
        it["has_thumb"] = bool(it.pop("thumb_path")) or it["source"] == "plex"
    ch = dict(row)
    if ch["source"] == "local":  # older channels were saved without an address; build it from the channel id
        ch["url"] = jobs.channel_url(ch["external_id"], ch["url"] or "")
    return {
        "channel": ch, "subscription": dict(sub) if sub else None, "profile_ids": profile_ids, "items": items,
    }


# A channel's YouTube list, kept for a while: switching tabs shouldn't ask YouTube again (2026-11-24). YouTube hands a
# channel out about 30 videos per request, so "everything" for a big channel is ~100 requests: asked for on purpose,
# and kept for an hour.
_YT_LISTS: dict[int, tuple[float, int, list]] = {}
YT_LIST_S = 3600
YT_MOST = 5000


@router.get("/channels/{cid}/youtube")
def channel_youtube(cid: int, request: Request, limit: int = 60, fresh: bool = False) -> dict:
    """The channel's newest videos on YouTube that are not in the library as approved: missing ones, ones a parent
    turned down, ones waiting in Approve, and failed downloads. For the channel page's "Not in library" tab."""
    limit = max(10, min(limit, YT_MOST))
    with _db(request).conn() as c:
        row = c.execute("SELECT source, external_id, url FROM containers WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise HTTPException(404, "No such channel.")
    if row["source"] != "local":
        raise HTTPException(422, "Only YouTube channels have a YouTube list.")
    url = jobs.channel_url(row["external_id"], row["url"] or "")
    if not url:
        raise HTTPException(422, "This channel has no YouTube address.")
    got = _YT_LISTS.get(cid)
    if got and not fresh and time.time() - got[0] < YT_LIST_S and got[1] >= limit:
        videos = got[2][:limit]
    else:
        base = subscriptions.channel_base(url)
        downloader = request.app.state.downloader
        try:
            try:
                videos = downloader.look(base + "/videos", limit=limit).videos
            except Exception:  # a channel with only Shorts or playlists has no Videos tab
                videos = downloader.look(base, limit=limit).videos
        except Exception as exc:
            raise HTTPException(502, f"Couldn't read the channel on YouTube: {exc}")
        _YT_LISTS[cid] = (time.time(), limit, videos)
    with _db(request).conn() as c:
        known = {r["external_id"]: r for r in c.execute(
            "SELECT id, external_id, approval, status FROM items WHERE source = 'local'")}
    out, in_library = [], 0
    for v in videos:
        k = known.get(v.external_id)
        if k is None:
            state = "missing"
        elif k["approval"] == "hidden":
            state = "rejected"
        elif k["approval"] == "waiting":
            state = "waiting"
        elif k["status"] == "failed":
            state = "failed"
        else:
            in_library += 1
            continue
        out.append({"external_id": v.external_id, "url": v.url, "title": v.title, "duration_s": v.duration_s,
                    "upload_date": v.upload_date, "is_short": v.is_short,
                    # A quick channel listing has no thumbnail address; YouTube's is fixed by the video id.
                    "thumb_url": v.thumb_url or f"https://i.ytimg.com/vi/{v.external_id}/mqdefault.jpg",
                    "state": state, "item_id": k["id"] if k is not None else None})
    return {"url": url, "checked": len(videos), "in_library": in_library, "more": len(videos) >= limit and limit < YT_MOST,
            "videos": out}


class ChannelPatch(BaseModel):
    trusted: bool | None = None
    rested_until: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    profile_ids: list[int] | None = None


@router.patch("/channels/{cid}")
def channel_patch(cid: int, body: ChannelPatch, request: Request) -> dict:
    with _db(request).conn() as c:
        if body.trusted is not None:
            c.execute("UPDATE containers SET trusted = ? WHERE id = ?", (int(body.trusted), cid))
        if body.rested_until is not None:
            c.execute("UPDATE containers SET rested_until = ? WHERE id = ?", (body.rested_until or None, cid))
        if body.profile_ids is not None:
            c.execute("DELETE FROM assignments WHERE container_id = ?", (cid,))
            for pid in body.profile_ids:
                c.execute("INSERT INTO assignments (profile_id, container_id) VALUES (?, ?)", (pid, cid))
    return {"ok": True}


class Rules(BaseModel):
    mode: str = Field(default="new", pattern="^(new|all|last)$")
    last_n: int = Field(default=10, ge=1, le=500)
    min_s: int = Field(default=0, ge=0)
    max_s: int = Field(default=0, ge=0)
    skip_shorts: bool = True
    skip_live: bool = True
    title_must: str = Field(default="", max_length=300)
    title_not: str = Field(default="", max_length=300)
    check_hours: int = Field(default=6, ge=1, le=168)
    daily_cap: int = Field(default=10, ge=1, le=200)
    keep_mode: str = Field(default="all", pattern="^(all|last|watched)$")
    keep_n: int = Field(default=30, ge=1, le=5000)
    keep_days: int = Field(default=60, ge=1, le=3650)
    active: bool = True


class SubscribeIn(BaseModel):
    url: str = Field(default="", max_length=500)
    container_id: int | None = None  # from a channel's page: the server finds (or builds) its address
    rules: Rules = Rules()
    profile_ids: list[int] | None = None
    trusted: bool = False


@router.post("/subscribe")
def subscribe(body: SubscribeIn, request: Request) -> dict:
    db = _db(request)
    url = body.url.strip()
    if len(url) < 8 and body.container_id:
        with db.conn() as c:
            row = c.execute("SELECT external_id, url FROM containers WHERE id = ? AND source = 'local'",
                            (body.container_id,)).fetchone()
        url = jobs.channel_url(row["external_id"], row["url"] or "") if row else ""
    if len(url) < 8:
        log.warning("subscribe refused: no address (url=%r, container_id=%r)", body.url, body.container_id)
        raise HTTPException(400, "This channel has no YouTube address to subscribe to. Paste its link in Add instead.")
    log.info("subscribe %s (container %s, mode %s, for %s)", url, body.container_id, body.rules.mode, body.profile_ids)
    pids = body.profile_ids
    if pids is None:
        with db.conn() as c:
            pids = [r["id"] for r in c.execute("SELECT id FROM profiles WHERE kind = 'child'")]
    rules = body.rules.model_dump()
    rules = {k: (int(v) if isinstance(v, bool) else v) for k, v in rules.items()}
    try:
        out = subscriptions.subscribe(db, request.app.state.downloader, url, rules, pids, body.trusted)
    except ValueError as exc:
        log.warning("subscribe %s refused: %s", url, exc)
        raise HTTPException(400, str(exc))
    except Exception as exc:
        log.exception("subscribe %s failed reading the channel", url)
        raise HTTPException(502, f"Could not read that channel: {exc}")
    log.info("subscribed %s -> subscription %s, channel %s", url, out.get("subscription_id"), out.get("container_id"))
    return out


@router.put("/subscriptions/{sid}")
def subscription_update(sid: int, body: Rules, request: Request) -> dict:
    values = {k: (int(v) if isinstance(v, bool) else v) for k, v in body.model_dump().items()}
    with _db(request).conn() as c:
        c.execute(f"UPDATE subscriptions SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?", (*values.values(), sid))
    return {"ok": True}


@router.post("/subscriptions/{sid}/check")
def subscription_check(sid: int, request: Request) -> dict:
    return subscriptions.check(_db(request), request.app.state.downloader, sid)


class SubscriptionPatch(BaseModel):
    active: bool


@router.patch("/subscriptions/{sid}")
def subscription_patch(sid: int, body: SubscriptionPatch, request: Request) -> dict:
    """Pause or resume one subscription's downloads (ADR 0042). Its videos and rules stay as they are."""
    with _db(request).conn() as c:
        if not c.execute("UPDATE subscriptions SET active = ? WHERE id = ?", (int(body.active), sid)).rowcount:
            raise HTTPException(404, "No such subscription.")
    return {"ok": True, "active": body.active}


# ---- channels nobody watches (ADR 0042) -----------------------------------------------------------------------------


@router.get("/unwatched")
def unwatched_list(request: Request) -> dict:
    return unwatched.report(_db(request), request.app.state.cfg.library_dir)


@router.post("/unwatched/{cid}/keep")
def unwatched_keep(cid: int, request: Request) -> dict:
    """Keep it: off the list for 90 days."""
    if not unwatched.keep(_db(request), cid):
        raise HTTPException(404, "No such channel.")
    return {"ok": True, "days": unwatched.KEEP_DAYS}


@router.delete("/unwatched/{cid}/keep")
def unwatched_unkeep(cid: int, request: Request) -> dict:
    """Undo "Keep it"."""
    with _db(request).conn() as c:
        c.execute("UPDATE containers SET kept_until = NULL WHERE id = ?", (cid,))
    return {"ok": True}


@router.delete("/subscriptions/{sid}")
def subscription_delete(sid: int, request: Request) -> dict:
    """Stop following the channel, and stop its waiting downloads. Videos already downloaded stay."""
    return {"ok": True, "stopped": subscriptions.unsubscribe(_db(request), sid)}


@router.delete("/channels/{cid}")
def channel_delete(cid: int, request: Request) -> dict:
    """Unsubscribe and delete all: the channel, every video from it and their files (a YouTube channel only;
    Plex shows are removed with /plex/containers)."""
    out = subscriptions.delete_channel(_db(request), request.app.state.cfg.library_dir, cid)
    if not out["found"]:
        raise HTTPException(404, "No such YouTube channel.")
    return out


# ---- one video ------------------------------------------------------------------------------------------------------


@router.get("/items/{item_id}/detail")
def item_detail(item_id: int, request: Request) -> dict:
    with _db(request).conn() as c:
        row = c.execute(
            "SELECT i.*, c.title AS container_title, c.thumb_url AS container_thumb, c.source AS container_source "
            "FROM items i JOIN containers c ON c.id = i.container_id WHERE i.id = ?",
            (item_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "No such video.")
        item = dict(row)
        for k in ("file_path", "media_key"):
            item.pop(k, None)
        item["has_thumb"] = bool(item.pop("thumb_path")) or item["source"] == "plex"
        item["item_profile_ids"] = [r[0] for r in c.execute("SELECT profile_id FROM assignments WHERE item_id = ?", (item_id,))]
        item["channel_profile_ids"] = [
            r[0] for r in c.execute("SELECT profile_id FROM assignments WHERE container_id = ?", (item["container_id"],))
        ]
        item["tags"] = sorted(
            {
                r[0]
                for r in c.execute(
                    "SELECT tag FROM tags WHERE (target_type = 'item' AND target_id = ?) OR "
                    "(target_type = 'container' AND target_id = ?)",
                    (item_id, item["container_id"]),
                )
            }
        )
        item["segments"] = [
            dict(r) for r in c.execute("SELECT id, start_s, end_s, category, origin FROM segments WHERE item_id = ? "
                                       "ORDER BY start_s", (item_id,))
        ]
        profiles = c.execute("SELECT id, name FROM profiles ORDER BY position, id").fetchall()
        item["why"] = {p["name"]: pipeline.explain(c, p["id"], item_id) for p in profiles}
        job = c.execute("SELECT state, progress, error FROM jobs WHERE item_id = ? ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
        item["job"] = dict(job) if job else None
    return item


@router.delete("/items/{item_id}")
def item_delete(item_id: int, request: Request) -> dict:
    """Delete a downloaded video's files and forget it. Plex items are only forgotten."""
    with _db(request).conn() as c:
        row = c.execute("SELECT source, file_path FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        if row["source"] == "local":
            subscriptions._delete_files(request.app.state.cfg.library_dir, row["file_path"])
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return {"ok": True}


@router.post("/items/approve-clean")
def approve_clean(request: Request) -> dict:
    """Approve every waiting video that has no blocked word and no warning."""
    with _db(request).conn() as c:
        n = c.execute(
            "UPDATE items SET approval = 'approved' WHERE approval = 'waiting' AND blocked_reason = ''"
        ).rowcount
    return {"approved": n}


class SegmentIn(BaseModel):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    category: str = Field(default="parent", max_length=30)


@router.post("/items/{item_id}/segments")
def segment_add(item_id: int, body: SegmentIn, request: Request) -> dict:
    if body.end_s <= body.start_s:
        raise HTTPException(422, "The end must be after the start.")
    with _db(request).conn() as c:
        sid = c.execute(
            "INSERT INTO segments (item_id, start_s, end_s, category, origin) VALUES (?, ?, ?, ?, 'parent')",
            (item_id, body.start_s, body.end_s, body.category),
        ).lastrowid
    return {"id": sid}


@router.delete("/segments/{seg_id}")
def segment_delete(seg_id: int, request: Request) -> dict:
    with _db(request).conn() as c:
        c.execute("DELETE FROM segments WHERE id = ?", (seg_id,))
    return {"ok": True}


# ---- the kids: now playing, time left, parent actions (ADR 0011) ----------------------------------------------------


@router.get("/kids")
def kids(request: Request) -> list[dict]:
    now = time.time()
    with _db(request).conn() as c:
        profiles = c.execute("SELECT * FROM profiles ORDER BY position, id").fetchall()
        out = []
        for p in profiles:
            ctx = clock.context(c, p["id"], now)
            dev = c.execute(
                "SELECT d.name AS tv, d.last_position_s, d.last_state, i.id AS item_id, i.title, i.duration_s, "
                "i.source, i.thumb_path, i.thumb_url FROM devices d JOIN items i ON i.id = d.last_item_id "
                "WHERE d.last_profile_id = ? AND d.last_heartbeat > ? AND d.revoked = 0 "
                "ORDER BY d.last_heartbeat DESC LIMIT 1",
                (p["id"], now - NOW_PLAYING_FRESH_S),
            ).fetchone()
            playing = None
            if dev:
                playing = {k: dev[k] for k in ("tv", "last_position_s", "last_state", "item_id", "title", "duration_s", "thumb_url")}
                playing["has_thumb"] = bool(dev["thumb_path"]) or dev["source"] == "plex"
            prof = dict(p)
            prof["avatar_url"] = avatar_url(prof["avatar"])
            out.append({"profile": prof, "time": ctx.public(), "reason": ctx.reason, "limits": ctx.limits, "playing": playing})
    return out


class KidAction(BaseModel):
    minutes: float = Field(default=0, ge=0, le=600)


@router.post("/kids/{pid}/{action}")
def kid_action(pid: int, action: str, body: KidAction, request: Request) -> dict:
    with _db(request).conn() as c:
        if not c.execute("SELECT 1 FROM profiles WHERE id = ?", (pid,)).fetchone():
            raise HTTPException(404, "No such profile.")
        try:
            clock.apply_action(c, pid, action, body.minutes)
        except ValueError:
            raise HTTPException(404, "Unknown action.")
        c.execute(
            "INSERT INTO events (ts, profile_id, type, data) VALUES (?, ?, 'parent', ?)",
            (time.time(), pid, json.dumps({"action": action, "minutes": body.minutes})),
        )
        return clock.context(c, pid).public()


class LimitsIn(BaseModel):
    weekday_min: int | None = Field(default=None, ge=0, le=1440)
    weekend_min: int | None = Field(default=None, ge=0, le=1440)
    session_min: int | None = Field(default=None, ge=0, le=1440)
    break_min: int = Field(default=60, ge=0, le=1440)
    closed_from: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    closed_to: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timefit: bool = True
    grace_min: int = Field(default=2, ge=0, le=30)
    show_timer: bool = True
    autoplay_n: int = Field(default=2, ge=0, le=20)


@router.get("/limits/{pid}")
def limits_get(pid: int, request: Request) -> dict:
    with _db(request).conn() as c:
        return clock.get_limits(c, pid)


@router.put("/limits/{pid}")
def limits_put(pid: int, body: LimitsIn, request: Request) -> dict:
    v = body.model_dump()
    v = {k: (int(x) if isinstance(x, bool) else x) for k, x in v.items()}
    cols = ", ".join(v)
    with _db(request).conn() as c:
        c.execute(
            f"INSERT INTO limits (profile_id, {cols}) VALUES (?, {', '.join('?' for _ in v)}) "
            f"ON CONFLICT (profile_id) DO UPDATE SET {', '.join(f'{k} = excluded.{k}' for k in v)}",
            (pid, *v.values()),
        )
    return {"ok": True}


# ---- Plex (ADR 0008) ------------------------------------------------------------------------------------------------


@router.get("/plex")
def plex_status(request: Request) -> dict:
    db = _db(request)
    st = plex.status(db)
    with db.conn() as c:
        st["allowed"] = [
            dict(r)
            for r in c.execute(
                "SELECT c.id, c.kind, c.title, c.external_id, "
                "(SELECT count(*) FROM items i WHERE i.container_id = c.id AND i.status = 'ready') AS ready, "
                "(SELECT count(*) FROM items i WHERE i.container_id = c.id AND i.status = 'failed') AS unplayable, "
                "(SELECT group_concat(a.profile_id) FROM assignments a WHERE a.container_id = c.id) AS profile_ids "
                "FROM containers c WHERE c.source = 'plex' ORDER BY c.title COLLATE NOCASE"
            )
        ]
        for a in st["allowed"]:
            a["profile_ids"] = _ids(a["profile_ids"])
        st["unplayable"] = [
            dict(r)
            for r in c.execute(
                "SELECT i.id, i.title, i.play_note, c.title AS container_title FROM items i "
                "JOIN containers c ON c.id = i.container_id WHERE i.source = 'plex' AND i.status = 'failed' "
                "ORDER BY c.title, i.title LIMIT 200"
            )
        ]
    return st


class PlexConfig(BaseModel):
    url: str = Field(max_length=300)
    token: str = Field(default="", max_length=200)


@router.put("/plex")
def plex_config(body: PlexConfig, request: Request) -> dict:
    db = _db(request)
    url = body.url.strip().rstrip("/")
    if not re.match(r"^https?://[^/\s]+$", url):
        raise HTTPException(422, "Use an address like http://192.168.1.10:32400")
    old_url, _ = plex.config(db)
    token = (body.token or "").strip()
    if url != old_url and not token:
        # A new address must come with the token again, so a saved token is never sent somewhere new.
        raise HTTPException(422, "Enter the Plex token again when changing the address.")
    db.set_setting("plex_url", url)
    if token:
        db.set_setting("plex_token", token)
    return plex.status(db)


@router.get("/plex/sections")
def plex_sections(request: Request) -> list[dict]:
    return plex.sections(_db(request))


@router.get("/plex/search")
def plex_search(q: str, request: Request) -> list[dict]:
    if len(q.strip()) < 2:
        raise HTTPException(422, "Type at least two letters.")
    return plex.search(_db(request), q.strip()[:100])


@router.get("/plex/poster/{rating_key}")
def plex_poster(rating_key: str, request: Request):
    if not re.fullmatch(r"\d{1,12}", rating_key):
        raise HTTPException(404)
    return plex.poster(request.app.state, rating_key)


@router.get("/plex/sections/{key}")
def plex_browse(key: str, request: Request, kind: str = "all") -> list[dict]:
    return plex.browse(_db(request), key, kind)


class AllowIn(BaseModel):
    rating_key: str = Field(pattern=r"^\d+$")
    profile_ids: list[int] | None = None


@router.post("/plex/allow")
def plex_allow(body: AllowIn, request: Request) -> dict:
    db = _db(request)
    pids = body.profile_ids
    if pids is None:
        with db.conn() as c:
            pids = [r["id"] for r in c.execute("SELECT id FROM profiles WHERE kind = 'child'")]
    return {"containers": plex.allow(db, body.rating_key, pids)}


@router.delete("/plex/containers/{cid}")
def plex_remove(cid: int, request: Request) -> dict:
    """Stop showing an allowed Plex show or collection. Nothing in Plex changes."""
    with _db(request).conn() as c:
        c.execute("DELETE FROM containers WHERE id = ? AND source = 'plex'", (cid,))
    return {"ok": True}


# ---- settings, storage, reports --------------------------------------------------------------------------------------


class SettingsIn(BaseModel):
    blocked_words: list[str] | None = None
    skip_categories: list[str] | None = None
    downloads_paused: bool | None = None
    storage_cap_gb: int | None = Field(default=None, ge=1, le=100000)
    level_volume: bool | None = None
    unwatched_days: int | None = Field(default=None, ge=1, le=365)


@router.get("/settings")
def settings_get(request: Request) -> dict:
    db = _db(request)
    lib = request.app.state.cfg.library_dir
    try:
        du = shutil.disk_usage(lib)
        disk = {"free_gb": round(du.free / 1e9), "total_gb": round(du.total / 1e9)}
    except OSError:
        disk = None
    with db.conn() as c:
        used = c.execute("SELECT count(*) FROM items WHERE source = 'local' AND status = 'ready'").fetchone()[0]
    size = sum(p.stat().st_size for p in lib.rglob("*.mp4")) if lib.exists() else 0
    return {
        "blocked_words": blocklist.words(db),
        "skip_categories": jobs.skip_categories(db),
        "downloads_paused": db.get_setting("downloads_paused") == "1",
        "storage_full": db.get_setting("storage_full") == "1",
        "storage_cap_gb": int(db.get_setting("storage_cap_gb") or 500),
        "library_gb": round(size / 1e9, 1),
        "library_videos": used,
        "disk": disk,
        "level_volume": loudness.is_on(db),
        "loudness": loudness.counts(db),
        "unwatched_days": unwatched.days_setting(db),
    }


@router.put("/settings")
def settings_put(body: SettingsIn, request: Request) -> dict:
    db = _db(request)
    if body.blocked_words is not None:
        blocklist.set_words(db, body.blocked_words)
    if body.skip_categories is not None:
        allowed = {"sponsor", "selfpromo", "interaction", "intro", "outro", "preview", "music_offtopic", "filler"}
        db.set_setting("skip_categories", json.dumps([x for x in body.skip_categories if x in allowed]))
    if body.downloads_paused is not None:
        db.set_setting("downloads_paused", "1" if body.downloads_paused else "0")
    if body.storage_cap_gb is not None:
        db.set_setting("storage_cap_gb", str(body.storage_cap_gb))
    if body.level_volume is not None:
        db.set_setting("level_volume", "1" if body.level_volume else "0")
    if body.unwatched_days is not None:
        db.set_setting("unwatched_days", str(body.unwatched_days))
    return settings_get(request)


@router.get("/reports")
def reports(profile_id: int, request: Request, days: int = 7) -> dict:
    now = time.time()
    keys = [clock.day_key(now - d * 86400) for d in range(days - 1, -1, -1)]
    with _db(request).conn() as c:
        per_day = {
            r["day"]: r["seconds"]
            for r in c.execute(
                f"SELECT day, seconds FROM watch_time WHERE profile_id = ? AND day IN ({','.join('?' for _ in keys)})",
                (profile_id, *keys),
            )
        }
        since = now - days * 86400
        top = [
            dict(r)
            for r in c.execute(
                "SELECT c.id, c.title, c.thumb_url, count(*) AS plays FROM events e JOIN items i ON i.id = e.item_id "
                "JOIN containers c ON c.id = i.container_id WHERE e.profile_id = ? AND e.type = 'started' AND e.ts > ? "
                "GROUP BY c.id ORDER BY plays DESC LIMIT 5",
                (profile_id, since),
            )
        ]
        again = [
            dict(r)
            for r in c.execute(
                # The same details as a history row: picture, channel, when and on which TV he last started it,
                # and whether he has ever watched it to the end.
                "SELECT i.id, i.title, i.duration_s, i.thumb_url, (i.thumb_path <> '' OR i.source = 'plex') AS has_thumb, "
                "c.id AS channel_id, c.title AS channel, count(*) AS plays, max(e.ts) AS last_ts, "
                "(SELECT d.name FROM events l LEFT JOIN devices d ON d.id = l.device_id WHERE l.profile_id = ? "
                "  AND l.item_id = i.id AND l.type = 'started' ORDER BY l.ts DESC LIMIT 1) AS tv, "
                "coalesce((SELECT w.watched FROM watch_state w WHERE w.profile_id = ? AND w.item_id = i.id), 0) AS finished "
                "FROM events e JOIN items i ON i.id = e.item_id LEFT JOIN containers c ON c.id = i.container_id "
                "WHERE e.profile_id = ? AND e.type = 'started' AND e.ts > ? GROUP BY i.id HAVING plays > 1 "
                "ORDER BY plays DESC, last_ts DESC LIMIT 5",
                (profile_id, profile_id, profile_id, since),
            )
        ]
        for r in again:
            r["has_thumb"], r["finished"] = bool(r["has_thumb"]), bool(r["finished"])
    return {"days": [{"day": k, "seconds": round(per_day.get(k, 0))} for k in keys], "channels": top, "again": again}


HISTORY_PAGE = 30


@router.get("/history")
def history(profile_id: int, request: Request, before: int | None = None, limit: int = HISTORY_PAGE) -> dict:
    """One boy's plays, newest first (ADR 0021): when, what, on which TV, and whether he watched to the end.
    `before` is the last id of the previous page."""
    limit = max(1, min(limit, 100))
    with _db(request).conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT e.id, e.ts, e.item_id, i.title, i.duration_s, i.thumb_url, (i.thumb_path <> '' OR i.source = 'plex') "
            "AS has_thumb, c.id AS channel_id, c.title AS channel, d.name AS tv, "
            # 'finished' for this video before his next play of anything
            "EXISTS (SELECT 1 FROM events f WHERE f.profile_id = e.profile_id AND f.item_id = e.item_id "
            "  AND f.type = 'finished' AND f.ts >= e.ts AND f.ts < coalesce((SELECT min(n.ts) FROM events n "
            "  WHERE n.profile_id = e.profile_id AND n.type = 'started' AND n.ts > e.ts), 1e18)) AS finished "
            "FROM events e LEFT JOIN items i ON i.id = e.item_id LEFT JOIN containers c ON c.id = i.container_id "
            "LEFT JOIN devices d ON d.id = e.device_id "
            "WHERE e.profile_id = ? AND e.type = 'started' AND (? IS NULL OR e.id < ?) ORDER BY e.id DESC LIMIT ?",
            (profile_id, before, before, limit + 1))]
        total = c.execute("SELECT count(*) FROM events WHERE profile_id = ? AND type = 'started'", (profile_id,)).fetchone()[0]
    for r in rows:
        r["has_thumb"], r["finished"] = bool(r["has_thumb"]), bool(r["finished"])
    return {"plays": rows[:limit], "more": len(rows) > limit, "total": total}


@router.delete("/history")
def clear_history(profile_id: int, request: Request) -> dict:
    """A parent clears one boy's history (ADR 0021): his plays and his resume points / watched marks. Minutes per day
    stay, so today's limit still counts; parent actions (extra time and so on) stay in the log."""
    with _db(request).conn() as c:
        if not c.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone():
            raise HTTPException(404, "No such profile.")
        plays = c.execute("DELETE FROM events WHERE profile_id = ? AND type IN ('started', 'finished')", (profile_id,)).rowcount
        c.execute("DELETE FROM watch_state WHERE profile_id = ?", (profile_id,))
    # His "Picked for you" row is left as it is: it rebuilds on its own schedule, now from the cleared history.
    return {"cleared": plays}
