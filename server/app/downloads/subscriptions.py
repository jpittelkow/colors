"""Channel subscriptions with rules, checked on a schedule (ADR 0004), and retention (ADR 0005).

A subscription belongs to one channel (a container). Assigning the channel to a profile covers every video in
it. New videos are approved without asking only on a trusted channel, and never when a blocked word matches.
"""
from __future__ import annotations

import glob
import logging
import re
import time
from pathlib import Path

from ..db import Database
from . import jobs
from .ytdlp import VideoInfo

log = logging.getLogger("kidtube.subs")

FIELDS = (
    "mode", "last_n", "min_s", "max_s", "skip_shorts", "skip_live", "title_must", "title_not", "check_hours",
    "daily_cap", "keep_mode", "keep_n", "keep_days", "active",
)
SHORT_MAX_S = 60


def channel_base(url: str) -> str:
    """https://www.youtube.com/@name/videos -> https://www.youtube.com/@name"""
    m = re.match(r"(https?://(?:www\.|m\.)?youtube\.com/(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+))", url)
    return m.group(1) if m else url.rstrip("/")


def _words(s: str) -> list[str]:
    return [w.strip().lower() for w in s.split(",") if w.strip()]


def passes(sub: dict, v: VideoInfo) -> str:
    """'' if the video passes the subscription's rules, else the reason it was left out."""
    if sub["skip_shorts"] and (v.is_short or (0 < v.duration_s <= SHORT_MAX_S)):
        return "Short"
    if sub["skip_live"] and v.is_live:
        return "Live stream"
    if sub["min_s"] and v.duration_s and v.duration_s < sub["min_s"]:
        return "Too short"
    if sub["max_s"] and v.duration_s and v.duration_s > sub["max_s"]:
        return "Too long"
    title = v.title.lower()
    must = _words(sub["title_must"])
    if must and not any(w in title for w in must):
        return "Title filter"
    if any(w in title for w in _words(sub["title_not"])):
        return "Title filter"
    return ""


def subscribe(db: Database, downloader, url: str, rules: dict, profile_ids: list[int], trusted: bool) -> dict:
    base = channel_base(url)
    listing = downloader.look(base + "/videos", limit=max(30, int(rules.get("last_n") or 10)))
    if not listing.videos and not listing.channel_id:
        raise ValueError("That link didn't lead to a channel with videos.")
    first = listing.videos[0] if listing.videos else VideoInfo("", "", "")
    first.channel_id = first.channel_id or listing.channel_id
    first.channel_title = first.channel_title or listing.title
    now = time.time()
    with db.conn() as c:
        cid = jobs.ensure_channel(c, first, url=base, avatar=listing.avatar_url, now=now)
        c.execute(
            "UPDATE containers SET trusted = ?, description = ?, title = CASE WHEN ? <> '' THEN ? ELSE title END "
            "WHERE id = ?",
            (1 if trusted else 0, listing.description, listing.title, listing.title, cid),
        )
        values = {k: rules[k] for k in FIELDS if k in rules}
        sub = c.execute("SELECT id FROM subscriptions WHERE container_id = ?", (cid,)).fetchone()
        if sub:
            sid = sub["id"]
        else:
            sid = c.execute(
                "INSERT INTO subscriptions (container_id, url, created_at) VALUES (?, ?, ?)", (cid, base, now)
            ).lastrowid
        if values:
            c.execute(
                f"UPDATE subscriptions SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?", (*values.values(), sid)
            )
        for pid in profile_ids:
            c.execute("INSERT OR IGNORE INTO assignments (profile_id, container_id) VALUES (?, ?)", (pid, cid))
        c.execute(  # an AI suggestion the parent just took up (ADR 0034)
            "UPDATE suggestions SET status = 'added' WHERE kind = 'channel' AND "
            "external_id = (SELECT external_id FROM containers WHERE id = ?)", (cid,))
        mode = c.execute("SELECT mode FROM subscriptions WHERE id = ?", (sid,)).fetchone()["mode"]
        if mode == "new" and not sub:
            # Everything on the channel today counts as old: only later uploads come in.
            for v in listing.videos:
                c.execute("INSERT OR IGNORE INTO sub_seen (sub_id, external_id) VALUES (?, ?)", (sid, v.external_id))
    if mode != "new" and not sub:
        check(db, downloader, sid, listing=listing)
    return {"subscription_id": sid, "container_id": cid}


def _queued_today(c, container_id: int) -> int:
    since = time.time() - 24 * 3600
    return c.execute(
        "SELECT count(*) FROM jobs j JOIN items i ON i.id = j.item_id WHERE i.container_id = ? AND j.created_at > ?",
        (container_id, since),
    ).fetchone()[0]


# Remember a video as seen, unless the parent unsubscribed meanwhile (the row would point at nothing).
SEEN = ("INSERT OR IGNORE INTO sub_seen (sub_id, external_id) SELECT ?, ? "
        "WHERE EXISTS (SELECT 1 FROM subscriptions WHERE id = ?)")


def check(db: Database, downloader, sub_id: int, *, listing=None) -> dict:
    """Look for videos the subscription has not seen and queue the ones that pass its rules."""
    with db.conn() as c:
        sub = c.execute(
            "SELECT s.*, c.trusted FROM subscriptions s JOIN containers c ON c.id = s.container_id WHERE s.id = ?",
            (sub_id,),
        ).fetchone()
    if not sub:
        return {"queued": 0}
    sub = dict(sub)
    want = sub["last_n"] if sub["mode"] == "last" else (400 if sub["mode"] == "all" else 30)
    try:
        listing = listing or downloader.look(sub["url"] + "/videos", limit=want)
    except Exception as exc:
        with db.conn() as c:
            c.execute(
                "UPDATE subscriptions SET last_checked = ?, last_error = ? WHERE id = ?",
                (time.time(), str(exc)[:500], sub_id),
            )
        log.warning("check of subscription %s (%s) failed: %s", sub_id, sub["url"], str(exc)[:300])
        return {"queued": 0, "error": str(exc)}
    videos = listing.videos[:want]
    if sub["mode"] == "all":
        videos = list(reversed(videos))  # oldest first, so a paced import fills in order
    queued, skipped = 0, 0
    with db.conn() as c:
        seen = {r[0] for r in c.execute("SELECT external_id FROM sub_seen WHERE sub_id = ?", (sub_id,))}
        room = max(0, sub["daily_cap"] - _queued_today(c, sub["container_id"]))
    for v in videos:
        if v.external_id in seen or not v.external_id:
            continue
        why = passes(sub, v)
        if why:
            skipped += 1
            with db.conn() as c:
                c.execute(SEEN, (sub_id, v.external_id, sub_id))
            continue
        if queued >= room:
            break  # paced: the rest stay unseen and come in on a later check
        with db.conn() as c:  # unsubscribed while this check ran: add nothing more
            if not c.execute("SELECT 1 FROM subscriptions WHERE id = ?", (sub_id,)).fetchone():
                break
        v.channel_id = v.channel_id or listing.channel_id
        jobs.add_video(db, v, approve=bool(sub["trusted"]), profile_ids=[], container_id=sub["container_id"])
        with db.conn() as c:
            c.execute(SEEN, (sub_id, v.external_id, sub_id))
        queued += 1
    with db.conn() as c:
        c.execute("UPDATE subscriptions SET last_checked = ?, last_error = '' WHERE id = ?", (time.time(), sub_id))
    if queued or skipped:
        log.info("check of subscription %s (%s): %d queued, %d left out by its rules", sub_id, sub["url"], queued, skipped)
    return {"queued": queued, "skipped": skipped}


def unsubscribe(db: Database, sub_id: int) -> int:
    """Stop following a channel, and stop downloading what the subscription queued: nothing more comes in from it.
    Videos already downloaded stay. Returns how many downloads it stopped (each shows as Stopped in Downloads and
    can be tried again from there by hand)."""
    with db.conn() as c:
        sub = c.execute("SELECT container_id FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
        if not sub:
            return 0
        # The subscription's own videos: what it saw and added (a video a parent added by hand is not in sub_seen).
        ids = [r[0] for r in c.execute(
            "SELECT i.id FROM items i JOIN sub_seen s ON s.external_id = i.external_id AND s.sub_id = ? "
            "WHERE i.container_id = ? AND i.source = 'local'", (sub_id, sub["container_id"]))]
        c.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
    stopped = jobs.stop_for_items(db, ids)
    log.info("unsubscribed %s (channel %s): %d downloads stopped", sub_id, sub["container_id"], stopped)
    return stopped


def delete_channel(db: Database, library_dir: Path, container_id: int) -> dict:
    """Unsubscribe and delete everything from one channel: its downloads stop, its video files go, and the channel
    leaves the library (its subscription, videos and who-sees-it go with it). Returns what it did."""
    with db.conn() as c:
        row = c.execute("SELECT id FROM containers WHERE id = ? AND source = 'local'", (container_id,)).fetchone()
        if not row:
            return {"found": False, "videos": 0, "stopped": 0}
        sub = c.execute("SELECT id FROM subscriptions WHERE container_id = ?", (container_id,)).fetchone()
        items = c.execute("SELECT id, file_path FROM items WHERE container_id = ?", (container_id,)).fetchall()
    stopped = unsubscribe(db, sub["id"]) if sub else 0
    stopped += jobs.stop_for_items(db, [r["id"] for r in items])  # videos added by hand from it too
    for r in items:
        _delete_files(library_dir, r["file_path"] or "")
    with db.conn() as c:
        c.execute("DELETE FROM containers WHERE id = ?", (container_id,))
    log.info("deleted channel %s: %d videos, %d downloads stopped", container_id, len(items), stopped)
    return {"found": True, "videos": len(items), "stopped": stopped}


def due(db: Database, now: float | None = None) -> list[int]:
    now = time.time() if now is None else now
    with db.conn() as c:
        return [
            r["id"]
            for r in c.execute(
                "SELECT id FROM subscriptions WHERE active = 1 AND "
                "(last_checked IS NULL OR last_checked < ? - check_hours * 3600)",
                (now,),
            )
        ]


def _delete_files(library_dir: Path, rel: str) -> None:
    if not rel:
        return
    f = library_dir / rel
    for p in f.parent.glob(glob.escape(f.stem) + ".*"):  # names contain [video id]
        try:
            p.unlink()
        except OSError:
            pass


def apply_retention(db: Database, library_dir: Path, now: float | None = None) -> int:
    """Delete downloaded files the subscription rules no longer keep. Returns how many videos were removed."""
    now = time.time() if now is None else now
    removed = 0
    with db.conn() as c:
        subs = c.execute("SELECT * FROM subscriptions WHERE keep_mode <> 'all'").fetchall()
        for s in subs:
            items = c.execute(
                "SELECT id, file_path FROM items WHERE container_id = ? AND source = 'local' AND status = 'ready' "
                "ORDER BY upload_date DESC, id DESC",
                (s["container_id"],),
            ).fetchall()
            doomed = []
            if s["keep_mode"] == "last":
                doomed = items[s["keep_n"]:]
            elif s["keep_mode"] == "watched":
                cutoff = now - s["keep_days"] * 86400
                for it in items:
                    profiles = {
                        r[0]
                        for r in c.execute(
                            "SELECT profile_id FROM assignments WHERE item_id = ? OR container_id = ?",
                            (it["id"], s["container_id"]),
                        )
                    }
                    done = {
                        r[0]
                        for r in c.execute(
                            "SELECT profile_id FROM watch_state WHERE item_id = ? AND watched = 1 AND updated_at < ?",
                            (it["id"], cutoff),
                        )
                    }
                    if profiles and profiles <= done:
                        doomed.append(it)
            for it in doomed:
                _delete_files(library_dir, it["file_path"])
                c.execute("DELETE FROM items WHERE id = ?", (it["id"],))
                removed += 1
    return removed
