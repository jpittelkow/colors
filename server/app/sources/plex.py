"""Plex as a source (ADR 0007, ADR 0008): allow-listed, streamed in place, read-only.

Nothing from Plex is shown until a parent allows a show, a movie or a collection. Allowing one copies its
metadata (not its files) into containers and items with source 'plex'. The token stays on the server; the TV gets
our own stream URL, and this module proxies the bytes from Plex.

Only direct play: a file the TVs can't play as it is (4K, or sound like DTS) is kept but marked 'failed' with a
note, so the parent sees it and the TV never does.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from ..db import Database

TIMEOUT_S = 15
OK_VIDEO = {"h264", "hevc"}
OK_AUDIO = {"aac", "ac3", "eac3", "mp3", "opus", "vorbis", "flac"}
MAX_HEIGHT = 1080


def config(db: Database) -> tuple[str, str]:
    url = db.get_setting("plex_url") or os.environ.get("KIDTUBE_PLEX_URL", "")
    token = db.get_setting("plex_token") or os.environ.get("KIDTUBE_PLEX_TOKEN", "")
    return url.rstrip("/"), token


def _get(db: Database, path: str, **params) -> dict:
    url, token = config(db)
    if not url or not token:
        raise HTTPException(400, "Plex is not connected. Add the Plex address and token in More > Plex.")
    q = urllib.parse.urlencode({**params, "X-Plex-Token": token})
    req = urllib.request.Request(f"{url}{path}?{q}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8")).get("MediaContainer", {})
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, f"Plex answered {exc.code} for {path}.")
    except OSError as exc:
        raise HTTPException(502, f"Could not reach Plex: {exc}")


def status(db: Database) -> dict:
    url, token = config(db)
    if not url or not token:
        return {"connected": False, "url": url}
    try:
        mc = _get(db, "/")
        return {"connected": True, "url": url, "name": mc.get("friendlyName", "Plex")}
    except HTTPException as exc:
        return {"connected": False, "url": url, "error": exc.detail}


def sections(db: Database) -> list[dict]:
    mc = _get(db, "/library/sections")
    return [
        {"key": d["key"], "title": d["title"], "type": d["type"]}
        for d in mc.get("Directory", [])
        if d.get("type") in ("show", "movie")
    ]


def browse(db: Database, section_key: str, kind: str = "all") -> list[dict]:
    """Shows or movies in a section (kind 'all'), or its collections (kind 'collections')."""
    path = f"/library/sections/{section_key}/{'collections' if kind == 'collections' else 'all'}"
    mc = _get(db, path)
    return [_card(m) for m in mc.get("Metadata", [])]


def _card(m: dict, section: str = "") -> dict:
    return {
        "rating_key": m["ratingKey"],
        "title": m.get("title", ""),
        "type": m.get("type", ""),
        "year": m.get("year"),
        "rating": m.get("contentRating", ""),
        "count": m.get("leafCount") or m.get("childCount"),
        "section": section or m.get("librarySectionTitle", ""),
    }


def search(db: Database, query: str, limit: int = 60) -> list[dict]:
    """Shows, movies and collections whose title contains the words, across every show and movie section."""
    out = []
    secs = sections(db)
    for kind in ("all", "collections"):  # shows and movies first, so they win over a collection of the same key
        for sec in secs:
            path = f"/library/sections/{sec['key']}/{kind}"
            for m in _get(db, path, title=query).get("Metadata", []):
                out.append(_card(m, sec["title"]))
    seen, uniq = set(), []
    for m in out:
        if m["rating_key"] not in seen:
            seen.add(m["rating_key"])
            uniq.append(m)
    q = query.lower()
    uniq.sort(key=lambda m: (not m["title"].lower().startswith(q), m["title"].lower()))
    return uniq[:limit]


def poster(state, rating_key: str):
    """A cached 2:3 poster for a show, movie or collection (the Plex page's grid)."""
    rk = int(rating_key)
    cache = Path(state.cfg.data_dir) / "plexposters" / f"{rk}.jpg"
    if not cache.is_file():
        url, token = config(state.db)
        if not url or not token:
            raise HTTPException(404)
        q = urllib.parse.urlencode(
            {"width": 240, "height": 360, "minSize": 1, "upscale": 1,
             "url": f"/library/metadata/{rk}/thumb", "X-Plex-Token": token}
        )
        try:
            with urllib.request.urlopen(f"{url}/photo/:/transcode?{q}", timeout=TIMEOUT_S) as r:
                data = r.read()
        except OSError:
            raise HTTPException(404)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return FileResponse(cache, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=604800"})


def _playable(m: dict) -> tuple[str, str]:
    """(media part key, note). An empty note means the TVs can play it as it is."""
    media = (m.get("Media") or [{}])[0]
    part = (media.get("Part") or [{}])[0]
    key = part.get("key", "")
    problems = []
    vc, ac = (media.get("videoCodec") or "").lower(), (media.get("audioCodec") or "").lower()
    height = int(media.get("height") or 0)
    if vc and vc not in OK_VIDEO:
        problems.append(f"{vc} video")
    if height > MAX_HEIGHT:
        problems.append("4K video" if height >= 2000 else f"{height}p video")
    if ac and ac not in OK_AUDIO:
        problems.append(f"{ac.upper()} sound")
    if not key:
        problems.append("no file")
    return key, ", ".join(problems)


def _upsert_container(c, kind: str, rating_key: str, title: str) -> int:
    c.execute(
        "INSERT INTO containers (source, kind, external_id, title, added_at) VALUES ('plex', ?, ?, ?, ?) "
        "ON CONFLICT (source, external_id) DO UPDATE SET title = excluded.title",
        (kind, rating_key, title, time.time()),
    )
    return c.execute("SELECT id FROM containers WHERE source = 'plex' AND external_id = ?", (rating_key,)).fetchone()["id"]


def _upsert_item(c, container_id: int, m: dict, kind: str) -> None:
    key, note = _playable(m)
    if kind == "episode":
        s, e = m.get("parentIndex"), m.get("index")
        prefix = f"S{s}E{e} " if s is not None and e is not None else ""
        title = f"{prefix}{m.get('title', '')}".strip()
    else:
        title = m.get("title", "")
    c.execute(
        "INSERT INTO items (container_id, source, external_id, kind, title, description, duration_s, upload_date, "
        "status, approval, play_note, media_key, added_at) VALUES (?, 'plex', ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?) "
        "ON CONFLICT (source, external_id) DO UPDATE SET title = excluded.title, duration_s = excluded.duration_s, "
        "status = excluded.status, play_note = excluded.play_note, media_key = excluded.media_key, "
        "container_id = excluded.container_id",
        (
            container_id, m["ratingKey"], "episode" if kind == "episode" else "movie", title,
            (m.get("summary") or "")[:2000], (m.get("duration") or 0) / 1000, m.get("originallyAvailableAt") or "",
            "failed" if note else "ready", note, key, time.time(),
        ),
    )


def allow(db: Database, rating_key: str, profile_ids: list[int]) -> list[int]:
    """Allow a show, movie or collection. Returns the container ids it now fills."""
    mc = _get(db, f"/library/metadata/{rating_key}")
    meta = (mc.get("Metadata") or [{}])[0]
    kind = meta.get("type")
    containers: list[int] = []
    with db.conn() as c:
        if kind == "show":
            containers.append(_sync_show(db, c, meta))
        elif kind == "movie":
            cid = _upsert_container(c, "collection", "plex-movies", "Movies")
            _upsert_item(c, cid, meta, "movie")
            containers.append(cid)
        elif kind == "collection":
            children = _get(db, f"/library/collections/{rating_key}/children").get("Metadata", [])
            cid = None
            for child in children:
                if child.get("type") == "show":
                    full = (_get(db, f"/library/metadata/{child['ratingKey']}").get("Metadata") or [child])[0]
                    containers.append(_sync_show(db, c, full))
                elif child.get("type") == "movie":
                    if cid is None:
                        cid = _upsert_container(c, "collection", rating_key, meta.get("title", "Collection"))
                        containers.append(cid)
                    detail = (_get(db, f"/library/metadata/{child['ratingKey']}").get("Metadata") or [child])[0]
                    _upsert_item(c, cid, detail, "movie")
        else:
            raise HTTPException(400, f"Plex item type {kind!r} can't be allowed.")
        for cid in containers:
            c.execute("UPDATE containers SET url = ? WHERE id = ? AND url = ''", (f"plex:{rating_key}", cid))
            for pid in profile_ids:
                c.execute("INSERT OR IGNORE INTO assignments (profile_id, container_id) VALUES (?, ?)", (pid, cid))
    return containers


def _sync_show(db: Database, c, meta: dict) -> int:
    cid = _upsert_container(c, "show", meta["ratingKey"], meta.get("title", "Show"))
    leaves = _get(db, f"/library/metadata/{meta['ratingKey']}/allLeaves").get("Metadata", [])
    for ep in leaves:
        _upsert_item(c, cid, ep, "episode")
    return cid


def resync(db: Database) -> int:
    """Pick up new episodes of allowed shows. Returns how many containers were refreshed."""
    url, token = config(db)
    if not url or not token:
        return 0
    with db.conn() as c:
        shows = c.execute("SELECT external_id FROM containers WHERE source = 'plex' AND kind = 'show'").fetchall()
    n = 0
    for s in shows:
        try:
            meta = (_get(db, f"/library/metadata/{s['external_id']}").get("Metadata") or [None])[0]
        except HTTPException:
            continue
        if meta:
            with db.conn() as c:
                _sync_show(db, c, meta)
            n += 1
    return n


def thumb(state, rating_key: str):
    """A cached 480x270 thumbnail for a Plex item."""
    cache = Path(state.cfg.data_dir) / "plexthumbs" / f"{int(rating_key)}.jpg"
    if not cache.is_file():
        url, token = config(state.db)
        if not url or not token:
            raise HTTPException(404)
        q = urllib.parse.urlencode(
            {"width": 480, "height": 270, "minSize": 1, "url": f"/library/metadata/{int(rating_key)}/thumb",
             "X-Plex-Token": token}
        )
        try:
            with urllib.request.urlopen(f"{url}/photo/:/transcode?{q}", timeout=TIMEOUT_S) as r:
                data = r.read()
        except OSError:
            raise HTTPException(404)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return FileResponse(cache, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


def stream(request: Request, media_key: str):
    """Proxy a Plex file to the TV, passing range requests through, so the token never leaves the server."""
    url, token = config(request.app.state.db)
    if not url or not token or not media_key.startswith("/library/parts/"):
        raise HTTPException(404, "This Plex video can't be streamed.")
    headers = {}
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]
    sep = "&" if "?" in media_key else "?"
    req = urllib.request.Request(f"{url}{media_key}{sep}X-Plex-Token={urllib.parse.quote(token)}", headers=headers)
    try:
        upstream = urllib.request.urlopen(req, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        raise HTTPException(exc.code if exc.code in (404, 416) else 502, "Plex could not send this video.")
    except OSError:
        raise HTTPException(502, "Could not reach Plex.")
    passthrough = {
        k: upstream.headers[k]
        for k in ("Content-Length", "Content-Range", "Accept-Ranges", "Content-Type")
        if upstream.headers.get(k)
    }

    def body():
        try:
            while chunk := upstream.read(256 * 1024):
                yield chunk
        finally:
            upstream.close()

    return StreamingResponse(body(), status_code=upstream.status, headers=passthrough)
