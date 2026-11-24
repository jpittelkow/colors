"""Parents' API for channel pictures (ADR 0030), background jobs and activity (ADR 0032), import (ADR 0035),
avatars (ADR 0036) and AI suggestions in the inbox (ADR 0034). All behind the admin password."""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import channel_pics
from ..db import Database
from ..downloads import importer
from . import downloads as downloads_api
from .admin import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

AVATAR_DIR = Path(__file__).resolve().parent.parent / "static" / "avatars"
# A household's own characters: <data dir>/characters/<name>.svg, beside the built-in set (ADR 0036). Set by
# create_app. They are the owner's files, not uploads, and never in the repo.
EXTRA_AVATAR_DIR: Path | None = None
CHARACTER_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
AVATAR_COLORS = ("coral", "grape", "sky", "sun", "mint", "leaf", "berry", "sand")


def _db(request: Request) -> Database:
    return request.app.state.db


# ---- channel pictures ----------------------------------------------------------------------------------------------


@router.get("/channel-pictures")
def pictures_ready(ids: str, request: Request) -> dict:
    """Which of these channels have a picture now. The page asks a few times after a search."""
    want = [i for i in ids.split(",") if channel_pics.valid(i)][:40]
    return {"ready": request.app.state.pics.ready(want)}


@router.get("/channel-pictures/{channel_id}")
def picture(channel_id: str, request: Request):
    pics = request.app.state.pics
    if not channel_pics.valid(channel_id):
        raise HTTPException(404)
    f = pics.file(channel_id)
    if not f and pics.known_url(channel_id):
        pics.fetch(channel_id)  # one picture whose address we already know: fetch it now
        f = pics.file(channel_id)
    if not f:
        pics.want([channel_id])
        raise HTTPException(404, "No picture yet.")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


# ---- background jobs and the activity popup ------------------------------------------------------------------------


@router.get("/activity")
def activity(request: Request) -> dict:
    """Everything the activity pill needs, in one small answer."""
    db, reg = _db(request), request.app.state.registry
    running = [{"name": r.job.name, "label": r.job.label, "note": r.note_text, "started_at": r.started,
                "stoppable": r.job.stoppable} for r in list(reg.running.values())]
    downloads = downloads_api.live(db)
    with db.conn() as c:
        queued = c.execute(
            "SELECT count(*) FROM jobs WHERE state = 'queued' AND (retry_at IS NULL OR retry_at <= ?)",
            (time.time(),)).fetchone()[0]
        retrying = c.execute(
            "SELECT count(*) FROM jobs WHERE state = 'queued' AND retry_at > ?", (time.time(),)).fetchone()[0]
        failed = c.execute("SELECT count(*) FROM jobs WHERE state = 'failed' AND stopped = 0").fetchone()[0]
        errors = [dict(r) for r in c.execute(
            "SELECT id, job, error, finished_at FROM job_runs WHERE state = 'failed' AND finished_at > ? "
            "ORDER BY id DESC LIMIT 5", (time.time() - 86400,))]
    labels = {j.name: j.label for j in reg.jobs.values()}
    for e in errors:
        e["label"] = labels.get(e["job"], e["job"])
    # A job that ran fine since its failure is no longer an error worth showing.
    last = reg.last_runs()
    errors = [e for e in errors if (last.get(e["job"]) or {}).get("id") == e["id"]]
    upcoming = [j for j in reg.describe() if j["next_at"] and not j["running"]]
    nxt = min(upcoming, key=lambda j: j["next_at"], default=None)
    return {
        "running": running, "downloads": downloads, "queued": queued, "retrying": retrying, "failed": failed, "errors": errors,
        "imports": import_notices(db),
        "next": {"label": nxt["label"], "at": nxt["next_at"]} if nxt else None, "now": time.time(),
        "downloads_paused": db.get_setting("downloads_paused") == "1",
        "storage_full": db.get_setting("storage_full") == "1",
        "checks_paused": db.get_setting("checks_paused") == "1",
    }


@router.get("/background-jobs")
def background_jobs(request: Request) -> dict:
    db = _db(request)
    try:
        versions = json.loads(db.get_setting("ytdlp_versions") or "{}")
    except ValueError:
        versions = {}
    reg = request.app.state.registry
    # Everything running, the hidden import jobs too, so the page's "Running now" is complete.
    running = sorted(({"name": r.job.name, "label": r.job.label, "note": r.note_text, "started_at": r.started,
                       "stoppable": r.job.stoppable, "listed": r.job.listed} for r in list(reg.running.values())),
                     key=lambda r: r["started_at"])
    return {"jobs": reg.describe(), "running": running, "now": time.time(),
            "checks_paused": db.get_setting("checks_paused") == "1", "ytdlp": versions}


@router.post("/background-jobs/{name}/run")
def background_run(name: str, request: Request) -> dict:
    reg = request.app.state.registry
    job = reg.jobs.get(name)
    if not job or not job.listed:
        raise HTTPException(404, "No such job.")
    if not job.enabled(_db(request)):
        raise HTTPException(409, job.disabled_note or "This job is switched off.")
    if not reg.start_job(name, by_hand=True):
        raise HTTPException(409, "It is already running.")
    return {"ok": True}


@router.post("/background-jobs/{name}/stop")
def background_stop(name: str, request: Request) -> dict:
    if not request.app.state.registry.stop_job(name):
        raise HTTPException(409, "Nothing to stop.")
    return {"ok": True}


@router.get("/background-jobs/{name}/history")
def background_history(name: str, request: Request) -> list[dict]:
    return request.app.state.registry.history(name)


class ScheduleIn(BaseModel):
    minutes: int = Field(ge=5, le=60 * 24 * 60)


@router.put("/background-jobs/{name}/schedule")
def background_schedule(name: str, body: ScheduleIn, request: Request) -> dict:
    job = request.app.state.registry.jobs.get(name)
    if not job or not job.listed or job.every_s is None:
        raise HTTPException(404, "No such scheduled job.")
    _db(request).set_setting(f"job_every:{name}", str(body.minutes * 60))
    return {"ok": True}


class PauseIn(BaseModel):
    checks_paused: bool


@router.put("/background-jobs/pause")
def background_pause(body: PauseIn, request: Request) -> dict:
    _db(request).set_setting("checks_paused", "1" if body.checks_paused else "0")
    return {"ok": True}


# ---- import --------------------------------------------------------------------------------------------------------


class ImportFile(BaseModel):
    """One Takeout file and the kids whose account it came from (none = everyone)."""

    text: str = Field(min_length=1, max_length=40_000_000)  # a watch history of a few years is about 10 MB
    profile_ids: list[int] = Field(default=[], max_length=50)


class ImportIn(BaseModel):
    source: str = Field(pattern="^(paste|takeout|playlist)$")
    text: str = Field(default="", max_length=2_000_000)
    files: list[ImportFile] = Field(default=[], max_length=12)
    min_watches: int = Field(default=3, ge=1, le=100)  # from a watch history: videos watched this often or more


@router.post("/import")
def import_start(body: ImportIn, request: Request) -> dict:
    db, reg = _db(request), request.app.state.registry
    if "import-read" in reg.running or "import-apply" in reg.running:
        raise HTTPException(409, "Another import is still running. It shows in the activity panel.")
    note = ""
    if body.source == "takeout" and body.files:
        with db.conn() as c:
            known = {r[0] for r in c.execute("SELECT id FROM profiles")}
        urls, note = importer.from_files(
            [(f.text, [p for p in f.profile_ids if p in known]) for f in body.files], body.min_watches)
    elif body.source == "takeout":
        urls = importer.parse_takeout(body.text)
    else:
        urls = importer.parse_links(body.text)
    if body.source == "playlist":
        urls = [u for u in urls if "list=" in u][:1]
        if not urls:
            raise HTTPException(422, "That is not a playlist link. It should contain “list=”.")
    try:
        iid = importer.create(db, body.source, urls, note)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    reg.start_job("import-read", by_hand=True, arg=iid)
    return {"id": iid, "links": len(urls)}


def _import_runs(reg, iid: int) -> list:
    """The running read or apply job of this import, if any."""
    out = []
    for name in ("import-read", "import-apply"):
        run = reg.running.get(name)
        arg = run.arg.get("import_id") if run and isinstance(run.arg, dict) else (run.arg if run else None)
        if run and arg == iid:
            out.append(run)
    return out


@router.get("/imports/open")
def import_open(request: Request) -> dict:
    """The newest import that is not finished, so the page can pick up where the parent left it."""
    with _db(request).conn() as c:
        row = c.execute("SELECT id, state FROM imports WHERE state IN ('reading', 'review', 'applying') "
                        "ORDER BY id DESC LIMIT 1").fetchone()
    return {"id": row["id"] if row else None, "state": row["state"] if row else None}


@router.get("/import/{iid}")
def import_get(iid: int, request: Request) -> dict:
    with _db(request).conn() as c:
        imp = c.execute("SELECT * FROM imports WHERE id = ?", (iid,)).fetchone()
        if not imp:
            raise HTTPException(404, "No such import.")
        shown = "import_id = ? AND NOT (kind = 'playlist' AND state = 'skipped')"
        total, waiting = c.execute(
            f"SELECT count(*), coalesce(sum(state = 'waiting'), 0) FROM import_rows WHERE {shown}", (iid,)).fetchone()
        # While it reads, the page only shows the last few: a watch history is over a thousand rows, asked for
        # every couple of seconds.
        tail = " AND state = 'read' ORDER BY id DESC LIMIT 5" if imp["state"] == "reading" else " ORDER BY id"
        rows = [dict(r) for r in c.execute(f"SELECT * FROM import_rows WHERE {shown}{tail}", (iid,))]
    pics = request.app.state.pics
    for r in rows:
        r["has_pic"] = bool(r["kind"] == "channel" and pics.file(r["channel_id"]))
        r["profile_ids"] = importer.profile_ids_of(r["profile_ids"])
    runs = _import_runs(request.app.state.registry, iid)
    try:  # what adding did so far: what downloads now and what does not (finish message, and after a Stop)
        result = json.loads(_db(request).get_setting(f"import_result:{iid}") or "null")
    except ValueError:
        result = None
    return {"import": dict(imp), "rows": rows, "progress": {"total": total, "done": total - waiting},
            "note": runs[0].note_text if runs else "", "result": result}


@router.post("/import/{iid}/seen")
def import_seen(iid: int, request: Request) -> dict:
    """The parent has looked at a ready or finished import: the activity pill stops pointing at it."""
    db = _db(request)
    if db.get_setting(f"import_seen:{iid}") is not None:
        db.set_setting(f"import_seen:{iid}", "1")
    return {"ok": True}


def import_notices(db) -> list[dict]:
    """Imports ready to review or finished that the parent has not opened since (only those marked unseen: older
    imports have no mark and stay quiet)."""
    with db.conn() as c:
        rows = c.execute("SELECT i.id, i.state FROM imports i JOIN settings s ON s.key = 'import_seen:' || i.id "
                         "WHERE s.value = '' AND i.state IN ('review', 'done') ORDER BY i.id DESC LIMIT 3").fetchall()
    out = []
    for r in rows:
        try:
            res = json.loads(db.get_setting(f"import_result:{r['id']}") or "{}")
        except ValueError:
            res = {}
        out.append({"id": r["id"], "state": r["state"], "stopped": bool(res.get("stopped_after") is not None and r["state"] == "review"),
                    "added": res.get("videos", 0) + res.get("waiting", 0) + res.get("channels_now", 0)
                    + res.get("channels_new", 0) + res.get("channels_allowed", 0)})
    return out


class Choice(BaseModel):
    row_id: int
    action: str = Field(pattern="^(subscribe|approve|skip)$")
    profile_ids: list[int] = []
    trusted: bool = False
    mode: str = Field(default="new", pattern="^(new|last)$")
    last_n: int = Field(default=10, ge=1, le=50)


class ApplyIn(BaseModel):
    choices: list[Choice] = Field(max_length=4000)


@router.post("/import/{iid}/apply")
def import_apply(iid: int, body: ApplyIn, request: Request) -> dict:
    reg = request.app.state.registry
    with _db(request).conn() as c:
        imp = c.execute("SELECT state FROM imports WHERE id = ?", (iid,)).fetchone()
    if not imp:
        raise HTTPException(404, "No such import.")
    if imp["state"] != "review":
        raise HTTPException(409, "This import is not ready to add yet.")
    arg = {"import_id": iid, "choices": [ch.model_dump() for ch in body.choices]}
    if not reg.start_job("import-apply", by_hand=True, arg=arg):
        raise HTTPException(409, "Another import is still being added.")
    return {"ok": True}


@router.delete("/import/{iid}")
def import_delete(iid: int, request: Request) -> dict:
    reg = request.app.state.registry
    for run in _import_runs(reg, iid):
        reg.stop_job(run.job.name)
    with _db(request).conn() as c:
        c.execute("DELETE FROM imports WHERE id = ?", (iid,))
    return {"ok": True}


# ---- avatars -------------------------------------------------------------------------------------------------------


def avatar_ids() -> list[str]:
    dirs = [d for d in (AVATAR_DIR, EXTRA_AVATAR_DIR) if d and d.is_dir()]
    return sorted({p.stem for d in dirs for p in d.glob("*.svg") if CHARACTER_NAME.fullmatch(p.stem)})


def avatar_file(name: str) -> Path | None:
    """A character's picture: the household's own first, then the built-in one."""
    if not CHARACTER_NAME.fullmatch(name):
        return None
    for d in (EXTRA_AVATAR_DIR, AVATAR_DIR):
        if d and (d / f"{name}.svg").is_file():
            return d / f"{name}.svg"
    return None


@router.get("/avatars")
def avatars() -> dict:
    return {"characters": avatar_ids(), "colors": list(AVATAR_COLORS)}


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    avatar: str | None = Field(default=None, max_length=40)
    avatar_color: str | None = Field(default=None, max_length=20)
    birthday: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    picks_on: bool | None = None


AVATAR_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


@router.post("/profiles/{pid}/avatar-image")
async def profile_avatar_image(pid: int, request: Request) -> dict:
    """A parent's own picture for a profile, for example the character the boys know (ADR 0036, amended)."""
    ext = AVATAR_TYPES.get((request.headers.get("content-type") or "").split(";")[0].strip())
    if not ext:
        raise HTTPException(415, "Use a PNG, JPEG, WebP or GIF picture.")
    data = await request.body()
    if not data or len(data) > 3_000_000:
        raise HTTPException(413, "Pictures can be up to 3 MB.")
    folder = request.app.state.cfg.data_dir / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f"{pid}-*.*"):
        old.unlink(missing_ok=True)
    name = f"{pid}-{secrets.token_hex(8)}.{ext}"  # not guessable from the profile id
    (folder / name).write_bytes(data)
    with _db(request).conn() as c:
        c.execute("UPDATE profiles SET avatar = ? WHERE id = ?", (f"custom:{name}:{int(time.time())}", pid))
    return {"ok": True}


def avatar_url(avatar: str) -> str:
    """Where the page and the TV load a profile's picture from."""
    if not avatar:
        return ""
    if avatar.startswith("custom:"):
        _, name, stamp = (avatar.split(":") + ["", ""])[:3]
        return f"/avatars/custom/{name}?v={stamp}"
    return f"/avatars/{avatar}.svg"


@router.patch("/profiles/{pid}")
def profile_patch(pid: int, body: ProfilePatch, request: Request) -> dict:
    if body.avatar is not None and body.avatar not in avatar_ids() and body.avatar != "":
        raise HTTPException(422, "Unknown character.")
    if body.avatar_color is not None and body.avatar_color not in AVATAR_COLORS:
        raise HTTPException(422, "Unknown colour.")
    sets = {k: v for k, v in body.model_dump().items() if v is not None}
    if "picks_on" in sets:
        sets["picks_on"] = int(sets["picks_on"])
    if "birthday" in sets:
        sets["birthday"] = sets["birthday"] or None
    if sets:
        with _db(request).conn() as c:
            c.execute(f"UPDATE profiles SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), pid))
    return {"ok": True}


def default_avatar(c) -> tuple[str, str]:
    """A character and colour no other profile has yet, so the boys can tell themselves apart (ADR 0036)."""
    used = {r[0] for r in c.execute("SELECT avatar FROM profiles")}
    used_colors = {r[0] for r in c.execute("SELECT avatar_color FROM profiles")}
    order = [a for a in ("fox", "rocket", "bear", "train", "owl", "whale", "lion", "digger") if a in avatar_ids()]
    order += [a for a in avatar_ids() if a not in order]
    pick = next((a for a in order if a not in used), order[0] if order else "")
    color = next((x for x in AVATAR_COLORS if x not in used_colors), AVATAR_COLORS[0])
    return pick, color


# ---- AI suggestions in the inbox -----------------------------------------------------------------------------------


@router.get("/suggestions")
def suggestion_list(request: Request, status: str = "new") -> list[dict]:
    with _db(request).conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM suggestions WHERE status = ? ORDER BY created_at DESC LIMIT 100", (status,))]
    pics = request.app.state.pics
    for r in rows:
        r["has_pic"] = bool(r["kind"] == "channel" and pics.file(r["external_id"]))
        r["for_profiles"] = [int(x) for x in r["for_profiles"].split(",") if x]
    if rows:
        pics.want([r["external_id"] for r in rows if r["kind"] == "channel"])
    return rows


@router.post("/suggestions/{sid}/dismiss")
def suggestion_dismiss(sid: int, request: Request) -> dict:
    with _db(request).conn() as c:
        c.execute("UPDATE suggestions SET status = 'dismissed' WHERE id = ?", (sid,))
    return {"ok": True}
