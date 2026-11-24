"""The download queue: rows in `jobs`, one worker thread, one download at a time (ADR 0004).

After a download: blocked words are checked again against the full description (ADR 0009), SponsorBlock
segments are fetched (ADR 0024), and English subtitles are recorded if yt-dlp found any.
"""
from __future__ import annotations

import glob
import json
import logging
import threading
import time
from pathlib import Path

from ..curation import blocklist
from ..db import Database
from . import progress
from .ytdlp import VideoInfo

log = logging.getLogger("kidtube.jobs")

DEFAULT_SKIP = ["sponsor", "selfpromo", "interaction"]


def skip_categories(db: Database) -> list[str]:
    raw = db.get_setting("skip_categories")
    if raw is None:
        return list(DEFAULT_SKIP)
    try:
        return [c for c in json.loads(raw) if isinstance(c, str)]
    except json.JSONDecodeError:
        return []


def channel_url(external_id: str, url: str = "") -> str:
    """A channel's address. Channels that came in with a single video or an import were saved without one, and
    subscribing to them then sent an empty address (a 422 the parent saw as "Check the values you entered")."""
    if url:
        return url
    return f"https://www.youtube.com/channel/{external_id}" if external_id.startswith("UC") else ""


def ensure_channel(c, v: VideoInfo, *, url: str = "", avatar: str = "", now: float | None = None) -> int:
    now = time.time() if now is None else now
    key = v.channel_id or f"unknown:{v.channel_title or 'Unknown'}"
    url = channel_url(key, url)
    c.execute(
        "INSERT INTO containers (source, kind, external_id, title, url, thumb_url, added_at) "
        "VALUES ('local', 'channel', ?, ?, ?, ?, ?) ON CONFLICT (source, external_id) DO UPDATE SET "
        "url = CASE WHEN excluded.url <> '' THEN excluded.url ELSE containers.url END, "
        "thumb_url = CASE WHEN excluded.thumb_url <> '' THEN excluded.thumb_url ELSE containers.thumb_url END",
        (key, v.channel_title or "Unknown", url, avatar, now),
    )
    return c.execute("SELECT id FROM containers WHERE source = 'local' AND external_id = ?", (key,)).fetchone()["id"]


def add_video(
    db: Database, v: VideoInfo, *, approve: bool, profile_ids: list[int], container_id: int | None = None
) -> tuple[int, bool]:
    """Put a video in the library and queue its download. Returns (item id, was it new).

    A blocked word in the title keeps it waiting for a parent, whatever `approve` says.
    """
    now = time.time()
    hit = blocklist.match(f"{v.title}\n{v.description}", blocklist.words(db))
    with db.conn() as c:
        row = c.execute("SELECT id FROM items WHERE source = 'local' AND external_id = ?", (v.external_id,)).fetchone()
        if row:  # never download the same video twice
            return row["id"], False
        cid = container_id or ensure_channel(c, v, now=now)
        item_id = c.execute(
            "INSERT INTO items (container_id, external_id, url, title, description, duration_s, upload_date, "
            "thumb_url, approval, blocked_reason, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid, v.external_id, v.url, v.title, v.description, v.duration_s, v.upload_date, v.thumb_url,
                "approved" if approve and not hit else "waiting", f"Blocked word: {hit}" if hit else "", now,
            ),
        ).lastrowid
        for pid in profile_ids:
            c.execute("INSERT OR IGNORE INTO assignments (profile_id, item_id) VALUES (?, ?)", (pid, item_id))
        c.execute("INSERT INTO jobs (item_id, created_at) VALUES (?, ?)", (item_id, now))
    return item_id, True


def rehome(c, item_id: int, v: VideoInfo) -> bool:
    """A video filed under "unknown" (YouTube gave no channel when it was added) moves to its real channel."""
    row = c.execute(
        "SELECT ct.id, ct.external_id FROM items i JOIN containers ct ON ct.id = i.container_id WHERE i.id = ?",
        (item_id,),
    ).fetchone()
    if not row or not row["external_id"].startswith("unknown:") or not v.channel_id:
        return False
    new = ensure_channel(c, v, url=f"https://www.youtube.com/channel/{v.channel_id}")
    if new == row["id"]:
        return False
    # Anyone who could see it through the old folder keeps seeing this video.
    c.execute(
        "INSERT OR IGNORE INTO assignments (profile_id, item_id) SELECT profile_id, ? FROM assignments "
        "WHERE container_id = ?", (item_id, row["id"]))
    c.execute("UPDATE items SET container_id = ? WHERE id = ?", (new, item_id))
    if not c.execute("SELECT 1 FROM items WHERE container_id = ? LIMIT 1", (row["id"],)).fetchone():
        c.execute("DELETE FROM containers WHERE id = ?", (row["id"],))
    return True


def repair_unknown(db: Database, downloader) -> int:
    """Look up videos still filed under "unknown" and move them to their channel. Returns how many moved."""
    with db.conn() as c:
        rows = c.execute(
            "SELECT i.id, i.url FROM items i JOIN containers ct ON ct.id = i.container_id "
            "WHERE ct.source = 'local' AND ct.external_id LIKE 'unknown:%' AND i.url <> '' LIMIT 50").fetchall()
    moved = 0
    for r in rows:
        try:
            v = downloader.look(r["url"], limit=1).videos[0]
        except Exception:
            continue
        with db.conn() as c:
            moved += 1 if rehome(c, r["id"], v) else 0
    return moved


def retry(db: Database, job_id: int, *, fresh: bool = True) -> None:
    """Put a failed download back in the queue. `fresh` (a parent asked) also resets its count of tries."""
    with db.conn() as c:
        c.execute(
            "UPDATE jobs SET state = 'queued', error = '', progress = 0, stopped = 0, finished_at = NULL, "
            f"retry_at = NULL{', attempts = 0' if fresh else ''} WHERE id = ? AND state = 'failed'", (job_id,))
        c.execute(
            "UPDATE items SET status = 'pending' WHERE id = (SELECT item_id FROM jobs WHERE id = ?) AND status = 'failed'",
            (job_id,),
        )


# YouTube refuses a request now and then for no lasting reason, and the same video works minutes later. So a
# failed download waits and tries again by itself: after 1 minute, then after 5 more. Only then is it "failed".
RETRY_DELAYS: tuple[float, ...] = (60, 300)
AUTO_ATTEMPTS = 6  # the 6-hourly retry job stops trying after this many tries in all; a parent can still try again


def retry_failed(db: Database, *, max_attempts: int | None = None) -> int:
    """Queue every failed download again. Ones a parent stopped stay stopped, and so do videos a parent turned
    down ("Not for them")."""
    sql = ("SELECT j.id FROM jobs j JOIN items i ON i.id = j.item_id "
           "WHERE j.state = 'failed' AND j.stopped = 0 AND i.approval <> 'hidden'")
    if max_attempts is not None:
        sql += f" AND j.attempts < {int(max_attempts)}"
    with db.conn() as c:
        ids = [r[0] for r in c.execute(sql)]
    for i in ids:
        retry(db, i, fresh=max_attempts is None)
    return len(ids)


def stop(db: Database, job_id: int) -> str:
    """Stop one download. A waiting one is taken out of the queue; a running one is told to stop."""
    with db.conn() as c:
        row = c.execute("SELECT state, item_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return "gone"
        if row["state"] == "queued":
            c.execute(
                "UPDATE jobs SET state = 'failed', stopped = 1, error = 'Stopped', finished_at = ? WHERE id = ?",
                (time.time(), job_id))
            c.execute("UPDATE items SET status = 'failed' WHERE id = ? AND status = 'pending'", (row["item_id"],))
            return "stopped"
    if row["state"] == "running":
        progress.request_cancel(job_id)
        return "stopping"
    return "finished"


def stop_for_items(db: Database, item_ids: list[int]) -> int:
    """Nothing more downloads for these videos: waiting and running downloads stop, and failed ones are marked
    stopped so the retry job leaves them. For an unsubscribe and for "Not for them". Returns how many it stopped."""
    if not item_ids:
        return 0
    marks = ",".join("?" for _ in item_ids)
    with db.conn() as c:
        rows = c.execute(f"SELECT id, state FROM jobs WHERE item_id IN ({marks}) AND (state IN ('queued', 'running') "
                         "OR (state = 'failed' AND stopped = 0))", item_ids).fetchall()
        failed = [r["id"] for r in rows if r["state"] == "failed"]
        if failed:
            c.execute(f"UPDATE jobs SET stopped = 1, retry_at = NULL WHERE id IN ({','.join('?' for _ in failed)})", failed)
    for r in rows:
        if r["state"] != "failed":
            stop(db, r["id"])
    return len(rows)


def _clean_partial(library_dir: Path, external_id: str) -> None:
    """Remove half-downloaded pieces of one video after a Stop."""
    if not external_id:
        return
    for p in library_dir.glob(f"*/*{glob.escape('[' + external_id + ']')}*"):
        if p.suffix in (".part", ".ytdl") or ".part-" in p.name or p.name.endswith((".part", ".ytdl")):
            try:
                p.unlink()
            except OSError:
                pass


def _rel(p: Path | None, root: Path) -> str:
    if not p:
        return ""
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def _subtitle(file_path: Path) -> Path | None:
    for cand in sorted(file_path.parent.glob(glob.escape(file_path.stem) + ".en*.vtt")):
        return cand
    return None


def run_one(db: Database, downloader, library_dir: Path) -> bool:
    """Run the oldest queued job. Returns False when the queue is empty."""
    with db.conn() as c:
        job = c.execute(
            "SELECT j.id, j.item_id, i.url, i.external_id FROM jobs j JOIN items i ON i.id = j.item_id "
            "WHERE j.state = 'queued' AND (j.retry_at IS NULL OR j.retry_at <= ?) ORDER BY j.id LIMIT 1",
            (time.time(),),
        ).fetchone()
        if not job:
            return False
        c.execute(
            "UPDATE jobs SET state = 'running', started_at = ?, attempts = attempts + 1 WHERE id = ?",
            (time.time(), job["id"]))

    job_id = job["id"]
    last = {"saved": 0.0, "at": 0.0, "phase": ""}
    progress.start(job_id)

    def on_progress(ev) -> None:
        if progress.cancel_requested(job_id):
            raise progress.Cancelled()
        if not isinstance(ev, dict):  # a plain 0..1 fraction
            ev = {"phase": "Downloading", "fraction": float(ev)}
        now = time.time()
        frac = ev.get("fraction")
        if ev.get("phase") != last["phase"] or now - last["at"] >= 0.25:
            last["at"], last["phase"] = now, ev.get("phase") or ""
            progress.update(
                job_id, phase=ev.get("phase") or "Downloading", percent=None if frac is None else round(frac * 100, 1),
                downloaded=ev.get("downloaded", 0), total=ev.get("total", 0), speed=ev.get("speed", 0.0),
                eta=ev.get("eta"))
        if frac is not None and abs(frac - last["saved"]) >= 0.02:
            last["saved"] = frac
            with db.conn() as c:
                c.execute("UPDATE jobs SET progress = ? WHERE id = ?", (frac, job_id))

    try:
        got = downloader.download(job["url"], on_progress)
        if progress.cancel_requested(job_id):
            raise progress.Cancelled()
        progress.set_phase(job_id, "Checking")
        info = got.info
        try:
            size = got.file_path.stat().st_size
        except OSError:
            size = 0
        hit = blocklist.match(f"{info.title}\n{info.description}", blocklist.words(db))
        segs = []
        seg_fn = getattr(downloader, "segments", None)
        if seg_fn:
            segs = seg_fn(job["external_id"], skip_categories(db))
        with db.conn() as c:
            c.execute(
                "UPDATE items SET status = 'ready', file_path = ?, thumb_path = ?, subtitle_path = ?, "
                "duration_s = CASE WHEN ? > 0 THEN ? ELSE duration_s END, "
                "upload_date = CASE WHEN ? <> '' THEN ? ELSE upload_date END, "
                "description = CASE WHEN ? <> '' THEN ? ELSE description END WHERE id = ?",
                (
                    _rel(got.file_path, library_dir), _rel(got.thumb_path, library_dir),
                    _rel(_subtitle(got.file_path), library_dir), info.duration_s, info.duration_s,
                    info.upload_date, info.upload_date, info.description, info.description, job["item_id"],
                ),
            )
            if hit:
                c.execute(
                    "UPDATE items SET approval = CASE WHEN approval = 'approved' THEN 'waiting' ELSE approval END, "
                    "blocked_reason = ? WHERE id = ?",
                    (f"Blocked word: {hit}", job["item_id"]),
                )
            c.execute("DELETE FROM segments WHERE item_id = ? AND origin = 'sponsorblock'", (job["item_id"],))
            for s in segs:
                c.execute(
                    "INSERT INTO segments (item_id, start_s, end_s, category) VALUES (?, ?, ?, ?)",
                    (job["item_id"], s["start_s"], s["end_s"], s["category"]),
                )
            if info.channel_title:
                c.execute(
                    "UPDATE containers SET title = ? WHERE id = (SELECT container_id FROM items WHERE id = ?) "
                    "AND title = 'Unknown'",
                    (info.channel_title, job["item_id"]),
                )
            rehome(c, job["item_id"], info)
            c.execute(
                "UPDATE jobs SET state = 'done', progress = 1, bytes = ?, finished_at = ?, error = '', retry_at = NULL "
                "WHERE id = ?",
                (size, time.time(), job_id),
            )
    except progress.Cancelled:
        log.info("download stopped by a parent for item %s", job["item_id"])
        _clean_partial(library_dir, job["external_id"])
        with db.conn() as c:
            c.execute(
                "UPDATE jobs SET state = 'failed', stopped = 1, error = 'Stopped', finished_at = ? WHERE id = ?",
                (time.time(), job_id))
            c.execute("UPDATE items SET status = 'failed' WHERE id = ?", (job["item_id"],))
    except Exception as exc:  # a failed download must never stop the queue
        with db.conn() as c:
            tries = c.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
            if tries <= len(RETRY_DELAYS):  # wait a little and try again before calling it failed
                wait = RETRY_DELAYS[tries - 1]
                log.info("download of item %s failed (try %s), trying again in %ss: %s", job["item_id"], tries, wait, exc)
                c.execute(
                    "UPDATE jobs SET state = 'queued', progress = 0, error = ?, retry_at = ? WHERE id = ?",
                    (str(exc)[:2000], time.time() + wait, job_id))
            else:
                log.warning("download failed for item %s after %s tries: %s", job["item_id"], tries, exc)
                c.execute(
                    "UPDATE jobs SET state = 'failed', error = ?, finished_at = ?, retry_at = NULL WHERE id = ?",
                    (str(exc)[:2000], time.time(), job_id))
                c.execute("UPDATE items SET status = 'failed' WHERE id = ?", (job["item_id"],))
    finally:
        progress.clear(job_id)
    return True


def library_bytes(library_dir: Path) -> int:
    return sum(p.stat().st_size for p in library_dir.rglob("*") if p.is_file()) if library_dir.exists() else 0


def storage_full(db: Database, library_dir: Path) -> bool:
    """True when the library has reached the size cap set in the page (ADR 0005). Recorded for the page to show."""
    cap_gb = int(db.get_setting("storage_cap_gb") or 500)
    full = library_bytes(library_dir) >= cap_gb * 1e9
    if (db.get_setting("storage_full") == "1") != full:
        db.set_setting("storage_full", "1" if full else "0")
    return full


class Worker(threading.Thread):
    def __init__(self, db: Database, downloader, library_dir: Path, delay_s: float = 5.0):
        super().__init__(name="kidtube-downloads", daemon=True)
        self.db, self.downloader, self.library_dir, self.delay_s = db, downloader, library_dir, delay_s
        self._halt = threading.Event()
        self._size_checked = 0.0
        self._full = False

    def run(self) -> None:
        with self.db.conn() as c:  # jobs cut off by a restart go back in the queue
            c.execute("UPDATE jobs SET state = 'queued', progress = 0 WHERE state = 'running'")
        while not self._halt.is_set():
            if self.db.get_setting("downloads_paused") == "1":
                self._halt.wait(5)
                continue
            if time.time() - self._size_checked > 60:
                self._size_checked = time.time()
                self._full = storage_full(self.db, self.library_dir)
            if self._full:
                self._halt.wait(30)
                continue
            try:
                worked = run_one(self.db, self.downloader, self.library_dir)
            except Exception:
                log.exception("job worker error")
                worked = False
            self._halt.wait(self.delay_s if worked else 2.0)

    def stop(self) -> None:
        self._halt.set()
