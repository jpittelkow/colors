"""The parents' API, behind the admin password (ADR 0018, ADR 0025)."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import Database
from ..downloads import jobs
from ..rules import pipeline
from ..security import check_password, hash_password
from ..sources import plex

COOKIE = "kt_admin"
SESSION_S = 30 * 24 * 3600

router = APIRouter(prefix="/api/admin")


def _db(request: Request) -> Database:
    return request.app.state.db


def _authed(request: Request) -> bool:
    db: Database = request.app.state.db
    if db.get_setting("admin_password_off") == "1":
        return True
    token = request.cookies.get(COOKIE)
    claims = request.app.state.signer.read(token) if token else None
    # Changing the password bumps the generation, which signs out every other session.
    return bool(claims and claims.get("gen", 0) == int(db.get_setting("session_gen") or 0))


def require_admin(request: Request) -> None:
    if not _authed(request):
        raise HTTPException(401, "Sign in to the admin page first.")


# ---- sign-in -------------------------------------------------------------------------------------------------------


class Password(BaseModel):
    password: str = Field(min_length=6, max_length=200)


def _start_session(request: Request, response: Response) -> None:
    gen = int(request.app.state.db.get_setting("session_gen") or 0)
    token = request.app.state.signer.sign({"admin": True, "gen": gen}, SESSION_S)
    response.set_cookie(COOKIE, token, max_age=SESSION_S, httponly=True, samesite="strict")


@router.get("/auth")
def auth_state(request: Request) -> dict:
    db = _db(request)
    return {"password_set": db.get_setting("admin_password") is not None, "authed": _authed(request)}


@router.post("/auth/setup")
def auth_setup(body: Password, request: Request, response: Response) -> dict:
    """First run only: whoever opens the admin page first sets the password."""
    db = _db(request)
    if db.get_setting("admin_password") is not None:
        raise HTTPException(409, "A password is already set.")
    db.set_setting("admin_password", hash_password(body.password))
    _start_session(request, response)
    return {"ok": True}


@router.post("/auth/login")
def auth_login(body: Password, request: Request, response: Response) -> dict:
    stored = _db(request).get_setting("admin_password")
    if not stored or not check_password(body.password, stored):
        time.sleep(1)
        raise HTTPException(401, "Wrong password.")
    _start_session(request, response)
    return {"ok": True}


@router.post("/auth/logout")
def auth_logout(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    return {"ok": True}


guarded = APIRouter(dependencies=[Depends(require_admin)])

# ---- profiles ------------------------------------------------------------------------------------------------------


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    kind: str = Field(default="child", pattern="^(child|guest|grownup)$")
    avatar: str = Field(default="", max_length=40)
    birthday: str | None = None


class PasswordChange(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=6, max_length=200)


@guarded.post("/auth/change")
def auth_change(body: PasswordChange, request: Request, response: Response) -> dict:
    db = _db(request)
    stored = db.get_setting("admin_password")
    if not stored or not check_password(body.current, stored):
        time.sleep(1)
        raise HTTPException(403, "The current password is wrong.")
    db.set_setting("admin_password", hash_password(body.new))
    db.set_setting("session_gen", str(int(db.get_setting("session_gen") or 0) + 1))
    _start_session(request, response)
    return {"ok": True}


@guarded.get("/profiles")
def profiles(request: Request) -> list[dict]:
    with _db(request).conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM profiles ORDER BY position, id")]
    from .extras import avatar_url

    for r in rows:
        r["avatar_url"] = avatar_url(r["avatar"])
    return rows


@guarded.post("/profiles")
def profile_create(body: ProfileIn, request: Request) -> dict:
    from .extras import default_avatar

    with _db(request).conn() as c:
        avatar, color = default_avatar(c)
        pid = c.execute(
            "INSERT INTO profiles (name, kind, avatar, avatar_color, birthday) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.kind, body.avatar or avatar, color, body.birthday),
        ).lastrowid
    return {"id": pid}


@guarded.put("/profiles/{profile_id}")
def profile_update(profile_id: int, body: ProfileIn, request: Request) -> dict:
    with _db(request).conn() as c:
        c.execute(
            "UPDATE profiles SET name = ?, kind = ?, avatar = ?, birthday = ? WHERE id = ?",
            (body.name, body.kind, body.avatar, body.birthday, profile_id),
        )
    return {"ok": True}


@guarded.delete("/profiles/{profile_id}")
def profile_delete(profile_id: int, request: Request) -> dict:
    with _db(request).conn() as c:
        c.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    return {"ok": True}


# ---- search and add ------------------------------------------------------------------------------------------------


def _video_out(v) -> dict:
    return {
        "external_id": v.external_id, "url": v.url, "title": v.title, "duration_s": v.duration_s,
        "upload_date": v.upload_date, "thumb_url": v.thumb_url, "channel_title": v.channel_title,
        "channel_id": v.channel_id, "is_short": v.is_short,
    }


def _mark_known(request: Request, videos: list[dict]) -> list[dict]:
    with _db(request).conn() as c:
        known = {r["external_id"] for r in c.execute("SELECT external_id FROM items WHERE source = 'local'")}
    for v in videos:
        v["in_library"] = v["external_id"] in known
    return videos


SEARCH_MOST = 300  # YouTube has no "skip": every "Show more" re-reads the result pages before it


@guarded.get("/search")
def search(q: str, request: Request, limit: int = 15) -> list[dict]:
    """The top `limit` YouTube results. "Show more" asks for 15 more than last time and keeps the ones it has not
    shown: YouTube reshuffles between two searches, so asking for "results 16 to 30" repeated half of the first 15."""
    limit = max(1, min(limit, SEARCH_MOST))
    try:
        found = request.app.state.downloader.search(q, count=limit)
    except Exception as exc:
        raise HTTPException(502, f"YouTube search failed: {exc}")
    out = _mark_known(request, [_video_out(v) for v in found])
    # Channel pictures come in the background (ADR 0030); the page asks again for the ones not ready.
    pics = request.app.state.pics
    ids = [v["channel_id"] for v in out if v["channel_id"]]
    pics.want(ids)
    ready = set(pics.ready(list(dict.fromkeys(ids))))
    for v in out:
        v["channel_pic"] = v["channel_id"] in ready
    return out


class LookIn(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


@guarded.post("/look")
def look(body: LookIn, request: Request) -> dict:
    """Say what a pasted URL is: one video, or a playlist or channel with its videos."""
    try:
        listing = request.app.state.downloader.look(body.url)
    except Exception as exc:
        raise HTTPException(502, f"Could not read that link: {exc}")
    is_channel = getattr(listing, "is_channel", False)
    url = body.url
    if is_channel:
        from ..downloads.subscriptions import channel_base

        url = channel_base(listing.channel_url or body.url)
    cid = getattr(listing, "channel_id", "")
    pics = request.app.state.pics
    if is_channel and cid and not pics.file(cid) and getattr(listing, "avatar_url", ""):
        pics.fetch(cid, url=listing.avatar_url)
    return {
        "channel_id": cid,
        "channel_pic": bool(cid and pics.file(cid)),
        "kind": listing.kind,
        "title": listing.title,
        "is_channel": is_channel,
        "avatar_url": getattr(listing, "avatar_url", ""),
        "url": url,
        "videos": _mark_known(request, [_video_out(v) for v in listing.videos]),
    }


class AddIn(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=200)
    approve: bool = False
    profile_ids: list[int] | None = None  # None = every child profile


@guarded.post("/add")
def add(body: AddIn, request: Request) -> dict:
    db = _db(request)
    profile_ids = body.profile_ids
    if profile_ids is None:
        with db.conn() as c:
            profile_ids = [r["id"] for r in c.execute("SELECT id FROM profiles WHERE kind = 'child'")]
    added, skipped, failed = [], [], []
    for url in body.urls:
        video, error = None, ""
        for attempt in range(2):
            try:
                video = request.app.state.downloader.look(url, limit=1).videos[0]
            except Exception as exc:
                video, error = None, str(exc)[:300]
                continue
            if video.channel_id:  # a complete answer
                break
        if video is None:
            failed.append({"url": url, "error": error})
            continue
        item_id, new = jobs.add_video(db, video, approve=body.approve, profile_ids=profile_ids)
        (added if new else skipped).append(item_id)
        with db.conn() as c:  # an AI suggestion that a parent just added (ADR 0034)
            c.execute("UPDATE suggestions SET status = 'added' WHERE kind = 'video' AND external_id = ?",
                      (video.external_id,))
    return {"added": added, "already_in_library": skipped, "failed": failed}


# ---- library, approval, assignment, tags ---------------------------------------------------------------------------


@guarded.get("/items")
def items(
    request: Request, approval: str | None = None, container_id: int | None = None, source: str | None = None,
    q: str | None = None, limit: int = 300, offset: int = 0, profile_id: int | None = None,
    hide_failed: bool = False, total: bool = False,
) -> list[dict] | dict:
    """Items, newest first. `total=true` answers {items, total} so the page can number its pages."""
    sql = (
        "SELECT i.id, i.container_id, c.title AS container_title, c.thumb_url AS container_thumb, "
        "c.external_id AS container_external_id, c.source AS container_source, c.trusted AS container_trusted, "
        "i.external_id, "
        "i.source, i.title, i.duration_s, i.upload_date, i.status, i.approval, i.added_at, i.thumb_url, "
        "i.blocked_reason, i.play_note, (i.thumb_path <> '' OR i.source = 'plex') AS has_thumb, "
        "(SELECT j.progress FROM jobs j WHERE j.item_id = i.id ORDER BY j.id DESC LIMIT 1) AS progress, "
        "(SELECT j.stopped FROM jobs j WHERE j.item_id = i.id ORDER BY j.id DESC LIMIT 1) AS stopped, "
        "(SELECT group_concat(a.profile_id) FROM assignments a WHERE a.item_id = i.id "
        " OR a.container_id = i.container_id) AS profile_ids, "
        "(SELECT group_concat(t.tag) FROM tags t WHERE (t.target_type = 'item' AND t.target_id = i.id) "
        " OR (t.target_type = 'container' AND t.target_id = i.container_id)) AS tags "
        "FROM items i JOIN containers c ON c.id = i.container_id WHERE 1 = 1"
    )
    params: list = []
    if approval:
        sql += " AND i.approval = ?"
        params.append(approval)
    if container_id:
        sql += " AND i.container_id = ?"
        params.append(container_id)
    if source:
        sql += " AND i.source = ?"
        params.append(source)
    if q:
        sql += " AND (i.title LIKE ? OR c.title LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if profile_id:
        sql += (" AND EXISTS (SELECT 1 FROM assignments a WHERE a.profile_id = ? "
                "AND (a.item_id = i.id OR a.container_id = i.container_id))")
        params.append(profile_id)
    if hide_failed:  # the Approve list: failed and stopped downloads belong to Downloads (ADR 0037)
        sql += " AND i.status <> 'failed'"
    count_sql, count_params = f"SELECT count(*) FROM ({sql})", list(params)
    sql += " ORDER BY i.added_at DESC, i.id DESC LIMIT ? OFFSET ?"
    params += [min(max(limit, 1), 1000), max(offset, 0)]
    with _db(request).conn() as c:
        rows = [dict(r) for r in c.execute(sql, params)]
        n = c.execute(count_sql, count_params).fetchone()[0] if total else None
    for r in rows:
        r["profile_ids"] = sorted({int(x) for x in (r["profile_ids"] or "").split(",") if x})
        r["tags"] = sorted({x for x in (r["tags"] or "").split(",") if x})
    return {"items": rows, "total": n} if total else rows


class ItemPatch(BaseModel):
    approval: str | None = Field(default=None, pattern="^(waiting|approved|hidden)$")


@guarded.patch("/items/{item_id}")
def item_patch(item_id: int, body: ItemPatch, request: Request) -> dict:
    with _db(request).conn() as c:
        if body.approval:
            c.execute("UPDATE items SET approval = ? WHERE id = ?", (body.approval, item_id))
            c.execute(
                "INSERT INTO events (ts, item_id, type, data) VALUES (?, ?, 'approval', ?)",
                (time.time(), item_id, body.approval),
            )
    return {"ok": True}


class DecideIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    approval: str = Field(pattern="^(approved|hidden|waiting)$")


@guarded.post("/items/decide")
def items_decide(body: DecideIn, request: Request) -> dict:
    """Approve or turn down several videos at once (a whole channel's worth on the Approve tab)."""
    now = time.time()
    with _db(request).conn() as c:
        for item_id in body.ids:
            c.execute("UPDATE items SET approval = ? WHERE id = ?", (body.approval, item_id))
            c.execute("INSERT INTO events (ts, item_id, type, data) VALUES (?, ?, 'approval', ?)",
                      (now, item_id, body.approval))
    return {"decided": len(body.ids)}


@guarded.get("/items/{item_id}/thumb")
def item_thumb(item_id: int, request: Request):
    with _db(request).conn() as c:
        row = c.execute("SELECT source, external_id, thumb_path FROM items WHERE id = ?", (item_id,)).fetchone()
    if row and row["source"] == "plex":
        return plex.thumb(request.app.state, row["external_id"])
    if not row or not row["thumb_path"]:
        raise HTTPException(404)
    return FileResponse(
        request.app.state.cfg.library_dir / row["thumb_path"], headers={"Cache-Control": "private, max-age=86400"}
    )


@guarded.get("/containers")
def containers(request: Request) -> list[dict]:
    with _db(request).conn() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT c.*, (SELECT count(*) FROM items i WHERE i.container_id = c.id) AS item_count "
                "FROM containers c ORDER BY c.title COLLATE NOCASE"
            )
        ]


class AssignIn(BaseModel):
    profile_id: int
    item_id: int | None = None
    container_id: int | None = None
    on: bool = True


@guarded.post("/assign")
def assign(body: AssignIn, request: Request) -> dict:
    if (body.item_id is None) == (body.container_id is None):
        raise HTTPException(422, "Give an item or a container, not both.")
    with _db(request).conn() as c:
        if body.on:
            c.execute(
                "INSERT OR IGNORE INTO assignments (profile_id, item_id, container_id) VALUES (?, ?, ?)",
                (body.profile_id, body.item_id, body.container_id),
            )
        else:
            c.execute(
                "DELETE FROM assignments WHERE profile_id = ? AND item_id IS ? AND container_id IS ?",
                (body.profile_id, body.item_id, body.container_id),
            )
    return {"ok": True}


class TagIn(BaseModel):
    target_type: str = Field(pattern="^(item|container)$")
    target_id: int
    tag: str = Field(min_length=1, max_length=40)
    on: bool = True


@guarded.post("/tag")
def tag(body: TagIn, request: Request) -> dict:
    name = body.tag.strip().lower()
    with _db(request).conn() as c:
        if body.on:
            c.execute(
                "INSERT OR IGNORE INTO tags (target_type, target_id, tag) VALUES (?, ?, ?)",
                (body.target_type, body.target_id, name),
            )
        else:
            c.execute(
                "DELETE FROM tags WHERE target_type = ? AND target_id = ? AND tag = ?",
                (body.target_type, body.target_id, name),
            )
    return {"ok": True}


@guarded.get("/why")
def why(profile_id: int, item_id: int, request: Request) -> list[dict]:
    """Why can't he see this? Each pipeline step and its answer (ADR 0022)."""
    with _db(request).conn() as c:
        return pipeline.explain(c, profile_id, item_id)


# ---- downloads -----------------------------------------------------------------------------------------------------


@guarded.get("/jobs")
def job_list(request: Request) -> list[dict]:
    with _db(request).conn() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT j.*, i.title FROM jobs j LEFT JOIN items i ON i.id = j.item_id ORDER BY j.id DESC LIMIT 100"
            )
        ]


@guarded.post("/jobs/{job_id}/retry")
def job_retry(job_id: int, request: Request) -> dict:
    jobs.retry(_db(request), job_id)
    with _db(request).conn() as c:
        c.execute(
            "UPDATE items SET status = 'pending' WHERE id = (SELECT item_id FROM jobs WHERE id = ?) "
            "AND status = 'failed'",
            (job_id,),
        )
    return {"ok": True}


# ---- TVs -----------------------------------------------------------------------------------------------------------


@guarded.get("/devices")
def devices(request: Request) -> list[dict]:
    with _db(request).conn() as c:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id, name, paired_at, revoked, last_seen FROM devices WHERE paired_at IS NOT NULL ORDER BY id"
            )
        ]


class PairIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=1, max_length=40)


@guarded.post("/devices/pair")
def device_pair(body: PairIn, request: Request) -> dict:
    """A parent types the code a new TV is showing (ADR 0018)."""
    cutoff = time.time() - 15 * 60
    with _db(request).conn() as c:
        row = c.execute(
            "SELECT id FROM devices WHERE pair_code = ? AND paired_at IS NULL AND created_at > ?",
            (body.code, cutoff),
        ).fetchone()
        if not row:
            raise HTTPException(404, "No TV is showing that code. Codes last 15 minutes.")
        c.execute(
            "UPDATE devices SET name = ?, paired_at = ?, pair_code = NULL WHERE id = ?",
            (body.name, time.time(), row["id"]),
        )
    return {"id": row["id"]}


@guarded.delete("/devices/{device_id}")
def device_revoke(device_id: int, request: Request) -> dict:
    with _db(request).conn() as c:
        c.execute("UPDATE devices SET revoked = 1 WHERE id = ?", (device_id,))
    return {"ok": True}


router.include_router(guarded)
