"""Importing what the boys already have approved (ADR 0035).

Three ways in (pasted links, Google Takeout files, a playlist link) all become rows of one import. A background
job reads each link, slowly; the parent reviews the rows; a second job applies the choices, paced.

Takeout files are subscriptions.csv, a playlist CSV, or a watch history. A watch history only lists video links, so
the videos watched most are read one by one and then grouped under the channels they turned out to come from.
"""
from __future__ import annotations

import csv
import io
import json
import re
import time
from collections import Counter
from dataclasses import dataclass

from ..db import Database
from . import jobs, subscriptions
from .ytdlp import VideoInfo

MAX_ROWS = 500
MAX_WATCHED = 1500  # videos from a watch history in one import, most watched first
PAUSE_S = 1.5  # between YouTube lookups
CHANNEL_RE = re.compile(r"youtube\.com/(@[^/?#\s]+|channel/[^/?#\s]+|c/[^/?#\s]+|user/[^/?#\s]+)", re.I)
URL_RE = re.compile(r"(https?://[^\s,;<>\"']+|(?:www\.|m\.)?youtube\.com/[^\s,;<>\"']+|youtu\.be/[^\s,;<>\"']+)", re.I)
HANDLE_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9._-]{3,30})\b")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
WATCH_LINK_RE = re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})", re.I)


@dataclass
class Link:
    """One link of an import: how often it was watched (0 = not from a watch history) and who it is for."""

    url: str
    watches: int = 0
    profile_ids: tuple[int, ...] = ()


def kind_of(url: str) -> str:
    if "list=" in url and "watch?v=" not in url:
        return "playlist"
    if CHANNEL_RE.search(url) and "watch?v=" not in url:
        return "channel"
    return "video"


def parse_links(text: str) -> list[str]:
    """Every YouTube link (and @handle) in pasted text, once each, in order."""
    out = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(1).rstrip(".)]}")
        if not u.lower().startswith("http"):
            u = "https://" + u
        if "youtube.com" in u.lower() or "youtu.be" in u.lower():
            out.append(u)
    stripped = URL_RE.sub(" ", text or "")
    out += [f"https://www.youtube.com/@{h}" for h in HANDLE_RE.findall(stripped)]
    return list(dict.fromkeys(out))


def parse_takeout(data: str) -> list[str]:
    """Links from a Takeout CSV: subscriptions.csv (channels) or a playlist CSV (video ids)."""
    text = data.lstrip("﻿")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if row.get("channel url"):
            out.append(row["channel url"].replace("http://", "https://"))
        elif row.get("channel id"):
            out.append(f"https://www.youtube.com/channel/{row['channel id']}")
        elif VIDEO_ID_RE.match(row.get("video id", "")):
            out.append(f"https://www.youtube.com/watch?v={row['video id']}")
    return list(dict.fromkeys(out))


def is_history(data: str) -> bool:
    """A Takeout watch history (watch-history.html or .json), as opposed to one of its CSVs."""
    return data.lstrip("﻿ \t\r\n")[:1] in ("<", "[")


def parse_history(data: str) -> dict[str, int]:
    """How many times each video was watched, from a Takeout watch history. Adverts are left out.

    The file lists one entry per watch, newest first, and for a YouTube Kids account gives only the link: no
    title and no channel. Other entries (searches, visits) have no video link and are passed over.
    """
    text = data.lstrip("﻿ \t\r\n")
    seen: Counter[str] = Counter()
    if text.startswith("["):
        try:
            entries = json.loads(text)
        except ValueError:
            return {}
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict):
                continue
            if any(isinstance(d, dict) and d.get("name") == "From Google Ads" for d in e.get("details") or []):
                continue
            m = WATCH_LINK_RE.search(str(e.get("titleUrl") or ""))
            if m:
                seen[m.group(1)] += 1
        return dict(seen)
    for cell in text.split('class="outer-cell')[1:]:
        if "From Google Ads" in cell:
            continue
        m = WATCH_LINK_RE.search(cell)
        if m:
            seen[m.group(1)] += 1
    return dict(seen)


def from_files(files: list[tuple[str, list[int]]], min_watches: int = 3) -> tuple[list[Link], str]:
    """The links in uploaded Takeout files, each file with the kids it belongs to.

    A link in two kids' files is for both, and its watches add up. From a watch history only the videos one kid
    watched `min_watches` times or more come in. Returns the links and a line for the parent about what was kept.
    """
    merged: dict[str, Link] = {}
    in_history: set[str] = set()
    for data, pids in files:
        if is_history(data):
            counts = parse_history(data)
            in_history.update(counts)
            pairs = [(f"https://www.youtube.com/watch?v={vid}", n) for vid, n in counts.items() if n >= min_watches]
        else:
            pairs = [(u, 0) for u in parse_takeout(data)]
        for url, n in pairs:
            link = merged.setdefault(url, Link(url))
            link.watches += n
            link.profile_ids = tuple(dict.fromkeys(link.profile_ids + tuple(pids)))
    plain = [link for link in merged.values() if not link.watches]
    watched = sorted((link for link in merged.values() if link.watches), key=lambda link: -link.watches)
    note = ""
    if in_history:
        note = (f"The watch history has {len(in_history)} different videos; {len(watched)} of them were watched "
                f"{min_watches} times or more.")
        if len(watched) > MAX_WATCHED:
            note += f" Only the {MAX_WATCHED} watched most are here."
    return plain + watched[:MAX_WATCHED], note


def create(db: Database, source: str, urls: list[str | Link], note: str = "") -> int:
    links = [u if isinstance(u, Link) else Link(u) for u in urls]
    if not links:
        raise ValueError("No YouTube links found.")
    plain = sum(1 for link in links if not link.watches)
    if plain > MAX_ROWS:
        raise ValueError(f"That is {plain} links. Import at most {MAX_ROWS} at a time.")
    if len(links) - plain > MAX_WATCHED:
        raise ValueError(f"Import at most {MAX_WATCHED} watched videos at a time.")
    with db.conn() as c:
        iid = c.execute("INSERT INTO imports (source, created_at, note) VALUES (?, ?, ?)",
                        (source, time.time(), note)).lastrowid
        for link in links:
            c.execute("INSERT INTO import_rows (import_id, url, watches, profile_ids) VALUES (?, ?, ?, ?)",
                      (iid, link.url, link.watches, ",".join(str(p) for p in link.profile_ids)))
    return iid


def profile_ids_of(text: str) -> list[int]:
    return [int(x) for x in (text or "").split(",") if x.strip().isdigit()]


def _channels_of_watched(c, iid: int, containers: set) -> list[str]:
    """A channel row for every channel the watched videos came from, so a parent can take or leave it as a whole.

    A channel that is already a row (from subscriptions.csv) just gets its watches. A new row is not looked up on
    YouTube: it has no video count, and its picture comes later (ADR 0030). Returns the channel ids.
    """
    groups: dict[str, dict] = {}
    for r in c.execute(
            "SELECT channel_id, channel_title, watches, profile_ids FROM import_rows WHERE import_id = ? "
            "AND kind = 'video' AND state = 'read' AND watches > 0 AND channel_id <> '' ORDER BY id",
            (iid,)).fetchall():
        g = groups.setdefault(r["channel_id"], {"title": r["channel_title"], "watches": 0, "pids": {}, "all": False})
        g["watches"] += r["watches"]
        g["all"] = g["all"] or not r["profile_ids"]
        g["pids"].update(dict.fromkeys(profile_ids_of(r["profile_ids"])))
    for cid, g in groups.items():
        row = c.execute("SELECT id FROM import_rows WHERE import_id = ? AND kind = 'channel' AND state = 'read' "
                        "AND external_id = ?", (iid, cid)).fetchone()
        if row:
            c.execute("UPDATE import_rows SET watches = ? WHERE id = ?", (g["watches"], row["id"]))
            continue
        c.execute(
            "INSERT INTO import_rows (import_id, url, kind, state, external_id, title, channel_id, channel_title, "
            "watches, profile_ids, in_library) VALUES (?, ?, 'channel', 'read', ?, ?, ?, ?, ?, ?, ?)",
            (iid, f"https://www.youtube.com/channel/{cid}", cid, g["title"], cid, g["title"], g["watches"],
             "" if g["all"] else ",".join(str(p) for p in g["pids"]), int(cid in containers)))
    return list(groups)


def _known(c) -> tuple[set, set]:
    return ({r[0] for r in c.execute("SELECT external_id FROM containers WHERE source = 'local'")},
            {r[0] for r in c.execute("SELECT external_id FROM items WHERE source = 'local'")})


def _save_video(c, row_id: int, v: VideoInfo, items: set) -> None:
    c.execute(
        "UPDATE import_rows SET kind = 'video', state = 'read', external_id = ?, title = ?, channel_id = ?, "
        "channel_title = ?, thumb_url = ?, duration_s = ?, in_library = ?, url = ? WHERE id = ?",
        (v.external_id, v.title, v.channel_id, v.channel_title, v.thumb_url, v.duration_s,
         int(v.external_id in items), v.url, row_id))


def unfinished(db: Database) -> int | None:
    """The import that was still being read when the server went down, for the job to pick back up."""
    with db.conn() as c:
        row = c.execute("SELECT id FROM imports WHERE state = 'reading' ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def read(run) -> str:
    """The job: read each waiting row of one import.

    A long import takes hours, so it has to live through a restart: rows already read keep their state, a run
    that is stopped leaves the import in 'reading', and the next run (started again at startup, see `unfinished`)
    carries on with the rows still waiting. Cancelling deletes the import, so a stopped run has nothing to tidy.
    """
    db, downloader, iid = run.db, run.state.downloader, int(run.arg)
    pics = getattr(run.state, "pics", None)
    cut_short = "Stopped before the end; it carries on when the server is back."
    with db.conn() as c:
        rows = c.execute("SELECT id, url FROM import_rows WHERE import_id = ? AND state = 'waiting' ORDER BY id",
                         (iid,)).fetchall()
        containers, items = _known(c)
    for n, r in enumerate(rows, 1):
        if run.stopped():
            return cut_short
        run.note(f"Reading {n} of {len(rows)}")
        url, kind = r["url"], kind_of(r["url"])
        try:
            if kind == "channel":
                base = subscriptions.channel_base(url)
                try:
                    l = downloader.look(base + "/videos", limit=50)
                except Exception:  # some channels have no Videos tab (only Shorts or playlists)
                    l = downloader.look(base, limit=50)
                cid = l.channel_id or (l.videos[0].channel_id if l.videos else "")
                with db.conn() as c:
                    c.execute(
                        "UPDATE import_rows SET kind = 'channel', state = 'read', external_id = ?, title = ?, "
                        "channel_id = ?, channel_title = ?, thumb_url = ?, video_count = ?, in_library = ?, url = ? "
                        "WHERE id = ?",
                        (cid, l.title, cid, l.title, l.avatar_url, len(l.videos), int(cid in containers), base, r["id"]))
                if pics and cid and l.avatar_url:
                    pics.fetch(cid, url=l.avatar_url)
            elif kind == "playlist":
                l = downloader.look(url, limit=200)
                with db.conn() as c:
                    for v in l.videos:
                        new = c.execute("INSERT INTO import_rows (import_id, url) VALUES (?, ?)", (iid, v.url)).lastrowid
                        _save_video(c, new, v, items)
                    c.execute("UPDATE import_rows SET kind = 'playlist', state = 'skipped', title = ? WHERE id = ?",
                              (l.title or "Playlist", r["id"]))
            else:
                l = downloader.look(url, limit=1)
                with db.conn() as c:
                    _save_video(c, r["id"], l.videos[0], items)
        except Exception as exc:
            with db.conn() as c:
                c.execute("UPDATE import_rows SET state = 'failed', error = ? WHERE id = ?", (str(exc)[:300], r["id"]))
        time.sleep(PAUSE_S)
    with db.conn() as c:
        # Duplicates inside one import (a video pasted and also in a playlist): keep the first.
        c.execute(
            "UPDATE import_rows SET state = 'skipped' WHERE import_id = ? AND state = 'read' AND id NOT IN "
            "(SELECT min(id) FROM import_rows WHERE import_id = ? AND state = 'read' GROUP BY kind, external_id)",
            (iid, iid))
        watched_channels = _channels_of_watched(c, iid, containers)
    # Their pictures, one at a time like the links: asking for a few hundred at once is what pacing is there to avoid.
    need = [cid for cid in watched_channels if pics and not pics.file(cid)]
    for n, cid in enumerate(need, 1):
        if run.stopped():
            return cut_short
        run.note(f"Channel pictures: {n} of {len(need)}")
        try:
            pics.fetch(cid)
        except Exception:  # a channel without a picture still shows, with its first letter
            pass
        time.sleep(PAUSE_S)
    with db.conn() as c:
        c.execute("UPDATE imports SET state = 'review' WHERE id = ?", (iid,))
        counts = c.execute("SELECT state, count(*) FROM import_rows WHERE import_id = ? GROUP BY state",
                           (iid,)).fetchall()
    db.set_setting(f"import_seen:{iid}", "")  # the activity pill says "ready to review" until the parent opens it
    got = dict((s, n) for s, n in counts)
    return f"Read {got.get('read', 0)} links" + (f", {got['failed']} could not be read" if got.get("failed") else "")


DEFAULT_RULES = {"mode": "new", "last_n": 10, "daily_cap": 5}


def apply(run) -> str:
    """The job: carry out the parent's choices. arg = {"import_id": n, "choices": [...]}."""
    db, downloader = run.db, run.state.downloader
    iid = int(run.arg["import_id"])
    choices = {int(ch["row_id"]): ch for ch in run.arg["choices"]}
    with db.conn() as c:
        c.execute("UPDATE imports SET state = 'applying' WHERE id = ?", (iid,))
        rows = c.execute("SELECT * FROM import_rows WHERE import_id = ? AND state = 'read' ORDER BY id",
                         (iid,)).fetchall()
    done = {"subscribe": 0, "approve": 0, "skip": 0}
    # What it means for downloads, for the finish message: what starts downloading now and what does not.
    result = {"videos": 0, "waiting": 0, "channels_now": 0, "channels_new": 0, "channels_allowed": 0,
              "skipped": 0, "failed": 0}
    for n, r in enumerate(rows, 1):
        if run.stopped():
            # Back to review: rows already added are done, the rest wait for the parent again (nothing is lost).
            with db.conn() as c:
                c.execute("UPDATE imports SET state = 'review' WHERE id = ?", (iid,))
            _keep_result(db, iid, result, stopped_after=n - 1, of=len(rows))
            return f"Stopped after {n - 1} of {len(rows)}; the rest wait in review"
        ch = choices.get(r["id"]) or {"action": "skip"}
        action = ch.get("action", "skip")
        pids = [int(p) for p in ch.get("profile_ids") or []]
        run.note(f"Adding {n} of {len(rows)}")
        try:
            if action == "skip":
                state = "skipped"
            elif r["kind"] == "channel" and action == "subscribe":
                rules = dict(DEFAULT_RULES)
                if ch.get("mode") in ("new", "last"):
                    rules["mode"] = ch["mode"]
                rules["last_n"] = max(1, min(50, int(ch.get("last_n") or 10)))
                subscriptions.subscribe(db, downloader, r["url"], rules, pids, bool(ch.get("trusted")))
                time.sleep(PAUSE_S)
                result["channels_now" if rules["mode"] == "last" else "channels_new"] += 1
                state = "done"
            elif r["kind"] == "channel":
                # Just approved: the channel and who sees it, nothing downloads until a parent adds videos.
                v = VideoInfo("", "", "", channel_id=r["channel_id"], channel_title=r["channel_title"] or r["title"])
                with db.conn() as c:
                    cid = jobs.ensure_channel(c, v, url=r["url"], avatar=r["thumb_url"])
                    if ch.get("trusted"):
                        c.execute("UPDATE containers SET trusted = 1 WHERE id = ?", (cid,))
                    for pid in pids:
                        c.execute("INSERT OR IGNORE INTO assignments (profile_id, container_id) VALUES (?, ?)",
                                  (pid, cid))
                result["channels_allowed"] += 1
                state = "done"
            else:
                v = VideoInfo(r["external_id"], r["url"], r["title"], duration_s=r["duration_s"],
                              thumb_url=r["thumb_url"], channel_id=r["channel_id"], channel_title=r["channel_title"])
                item_id, _ = jobs.add_video(db, v, approve=True, profile_ids=pids)
                with db.conn() as c:  # a blocked word keeps it waiting in Approve, whatever the parent chose here
                    held = c.execute("SELECT approval FROM items WHERE id = ?", (item_id,)).fetchone()["approval"] == "waiting"
                result["waiting" if held else "videos"] += 1
                state = "done"
            if state == "skipped":
                result["skipped"] += 1
            done["skip" if action == "skip" else ("subscribe" if action == "subscribe" and r["kind"] == "channel"
                                                  else "approve")] += 1
            with db.conn() as c:
                c.execute("UPDATE import_rows SET state = ? WHERE id = ?", (state, r["id"]))
        except Exception as exc:
            result["failed"] += 1
            with db.conn() as c:
                c.execute("UPDATE import_rows SET state = 'failed', error = ? WHERE id = ?", (str(exc)[:300], r["id"]))
    with db.conn() as c:
        c.execute("UPDATE imports SET state = 'done' WHERE id = ?", (iid,))
    _keep_result(db, iid, result)
    return f"Subscribed to {done['subscribe']}, approved {done['approve']}, skipped {done['skip']}"


def _keep_result(db: Database, iid: int, result: dict, **extra) -> None:
    """What this run did, added to what earlier runs of the same import did (a stopped one carries on later).
    The page's finish message reads it; `seen` is cleared so the activity pill tells the parent again."""
    key = f"import_result:{iid}"
    try:
        before = json.loads(db.get_setting(key) or "{}")
    except ValueError:
        before = {}
    total = {k: int(before.get(k, 0)) + v for k, v in result.items()}
    total.update(extra)
    if not extra:
        total.pop("stopped_after", None)
        total.pop("of", None)
    db.set_setting(key, json.dumps(total))
    db.set_setting(f"import_seen:{iid}", "")


def reopen_cut_off(db: Database) -> None:
    """At startup: an import a restart cut off while adding goes back to review. The parent's choices were only in
    the job, so it cannot carry on by itself; rows already added stay added. Returns None: nothing to start."""
    with db.conn() as c:
        c.execute("UPDATE imports SET state = 'review' WHERE state = 'applying'")
    return None
