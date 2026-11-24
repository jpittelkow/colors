"""The Downloads page (ADR 0032, revised 2026-11-23): what is downloading now with live progress, what is
waiting, and a searchable history, with Stop and Try again. Modelled on an earlier download manager's pipeline panel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import Database
from ..downloads import jobs, progress
from .admin import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

PAGE = 25
ROW = (
    "j.id AS job_id, j.item_id, j.state, j.stopped, j.progress, j.error, j.created_at, j.started_at, j.finished_at, "
    "j.retry_at, j.attempts, "
    "j.bytes, i.title, i.duration_s, i.thumb_url, (i.thumb_path <> '') AS has_thumb, i.approval, "
    "c.title AS channel, c.id AS container_id"
)
JOIN = "FROM jobs j JOIN items i ON i.id = j.item_id JOIN containers c ON c.id = i.container_id"


def _db(request: Request) -> Database:
    return request.app.state.db


def _out(r) -> dict:
    d = dict(r)
    d["thumb"] = f"/api/admin/items/{d['item_id']}/thumb" if d.pop("has_thumb") else d["thumb_url"]
    d.pop("thumb_url")
    d["status"] = (
        "stopped" if d["stopped"] else {"queued": "waiting", "running": "downloading", "done": "done"}.get(d["state"], "failed")
    )
    return d


def live(db: Database) -> list[dict]:
    """Running downloads with their live numbers. Also feeds the activity pill."""
    with db.conn() as c:
        rows = [_out(r) for r in c.execute(f"SELECT {ROW} {JOIN} WHERE j.state = 'running' ORDER BY j.id")]
    for d in rows:
        p = progress.get(d["job_id"]) or {}
        d.update(
            phase=p.get("phase") or "Getting ready", percent=p.get("percent"), downloaded=p.get("downloaded", 0),
            total=p.get("total", 0), speed=p.get("speed", 0), eta=p.get("eta"), stopping=bool(p.get("stopping")),
        )
    return rows


def counts(db: Database) -> dict:
    with db.conn() as c:
        rows = c.execute(
            "SELECT CASE WHEN stopped = 1 THEN 'stopped' WHEN state = 'queued' THEN 'waiting' "
            "WHEN state = 'running' THEN 'downloading' ELSE state END AS s, count(*) FROM jobs GROUP BY s").fetchall()
    out = {"waiting": 0, "downloading": 0, "done": 0, "failed": 0, "stopped": 0}
    out.update({r[0]: r[1] for r in rows})
    return out


@router.get("/downloads/active")
def active(request: Request) -> dict:
    """Polled every couple of seconds while the Downloads page is open."""
    db = _db(request)
    with db.conn() as c:
        queued = [_out(r) for r in c.execute(f"SELECT {ROW} {JOIN} WHERE j.state = 'queued' ORDER BY j.id LIMIT 30")]
    return {
        "active": live(db), "queued": queued, "counts": counts(db),
        "paused": db.get_setting("downloads_paused") == "1", "storage_full": db.get_setting("storage_full") == "1",
    }


@router.get("/downloads/history")
def history(request: Request, status: str = "all", q: str = "", page: int = 1) -> dict:
    """Finished downloads, newest first: done, failed and stopped."""
    where, params = "j.state IN ('done', 'failed')", []
    if status == "done":
        where = "j.state = 'done'"
    elif status == "failed":
        where = "j.state = 'failed' AND j.stopped = 0"
    elif status == "stopped":
        where = "j.stopped = 1"
    if q.strip():
        where += " AND (i.title LIKE ? OR c.title LIKE ?)"
        params += [f"%{q.strip()}%"] * 2
    page = max(1, page)
    with _db(request).conn() as c:
        total = c.execute(f"SELECT count(*) {JOIN} WHERE {where}", params).fetchone()[0]
        rows = [_out(r) for r in c.execute(
            f"SELECT {ROW} {JOIN} WHERE {where} ORDER BY COALESCE(j.finished_at, j.created_at) DESC, j.id DESC "
            "LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE))]
    return {"rows": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE))}


@router.post("/downloads/{job_id}/stop")
def stop(job_id: int, request: Request) -> dict:
    result = jobs.stop(_db(request), job_id)
    if result == "gone":
        raise HTTPException(404, "No such download.")
    return {"result": result}


@router.post("/downloads/{job_id}/retry")
def retry(job_id: int, request: Request) -> dict:
    jobs.retry(_db(request), job_id)
    return {"ok": True}


@router.post("/downloads/retry-failed")
def retry_failed(request: Request) -> dict:
    return {"queued": jobs.retry_failed(_db(request))}
