"""Weekly suggestions for the parents: channels and videos to consider adding (ADR 0034, ADR 0014).

The model only proposes search words. The server looks each one up with yt-dlp, so every suggestion in the inbox
is a real channel or video, and nothing is added until a parent taps Add.
"""
from __future__ import annotations

import time

from ..db import Database
from . import openrouter, people

SYSTEM = (
    "You help parents of young children find good YouTube channels and videos. Suggest calm, age-appropriate, "
    "gentle content: songs, nature, vehicles, animals, simple learning, stories, from established kids' channels. "
    "Avoid toy unboxing, prank, challenge, loud or clickbait channels, and anything scary. "
    "Answer only with JSON: {\"suggestions\": [{\"for\": [\"Child A\"], \"kind\": \"channel\" or \"video\", "
    "\"search\": \"words to search YouTube for\", \"reason\": \"one short sentence for the parent\"}]}. "
    "Give at most 8 suggestions. Do not suggest channels the family already has."
)

MAX_PER_RUN = 8
PAUSE_S = 1.0  # between YouTube lookups


def _context(conn) -> tuple[str, list[dict]]:
    kids = people.labels(conn)
    since = time.time() - 30 * 86400
    parts = []
    for k in kids:
        done = conn.execute(
            "SELECT i.title, c.title AS channel FROM watch_state w JOIN items i ON i.id = w.item_id "
            "JOIN containers c ON c.id = i.container_id WHERE w.profile_id = ? AND w.watched = 1 AND w.updated_at > ? "
            "ORDER BY w.updated_at DESC LIMIT 15", (k["id"], since)).fetchall()
        fav = conn.execute(
            "SELECT c.title, count(*) AS n FROM events e JOIN items i ON i.id = e.item_id "
            "JOIN containers c ON c.id = i.container_id WHERE e.profile_id = ? AND e.type = 'started' AND e.ts > ? "
            "GROUP BY c.id ORDER BY n DESC LIMIT 5", (k["id"], since)).fetchall()
        lines = [f"{people.label_text(k)}:"]
        lines.append("  Favourite channels: " + (", ".join(f"{r['title']} ({r['n']} plays)" for r in fav) or "none yet"))
        lines.append("  Recently finished: " + ("; ".join(f"{r['title']} ({r['channel']})" for r in done) or "nothing yet"))
        parts.append("\n".join(lines))
    have = [r[0] for r in conn.execute("SELECT title FROM containers ORDER BY added_at DESC LIMIT 80")]
    no = [r[0] for r in conn.execute(
        "SELECT title FROM suggestions WHERE status = 'dismissed' ORDER BY created_at DESC LIMIT 40")]
    text = "\n\n".join(parts) or "No viewing history yet."
    text += "\n\nChannels the family already has: " + (", ".join(have) or "none")
    if no:
        text += "\nThe parents already said no to: " + ", ".join(no)
    return text, kids


def run(db: Database, downloader, job=None) -> str:
    with db.conn() as c:
        text, kids = _context(c)
    answer = openrouter.chat(db, "suggestions", SYSTEM, text)
    by_label = {k["label"].lower(): k["id"] for k in kids}
    with db.conn() as c:
        have = {r[0] for r in c.execute("SELECT external_id FROM containers WHERE source = 'local'")}
        have_items = {r[0] for r in c.execute("SELECT external_id FROM items WHERE source = 'local'")}
        known = {(r[0], r[1]) for r in c.execute("SELECT kind, external_id FROM suggestions")}
    added = 0
    for s in (answer.get("suggestions") or [])[:MAX_PER_RUN]:
        if job and job.stopped():
            break
        if not isinstance(s, dict) or not str(s.get("search") or "").strip():
            continue
        query = str(s["search"])[:100]
        kind = "video" if s.get("kind") == "video" else "channel"
        whom = ",".join(str(by_label[str(x).lower()]) for x in (s.get("for") or []) if str(x).lower() in by_label)
        if job:
            job.note(f"Looking up “{query}”")
        try:
            found = downloader.search(query, count=5)
        except Exception:
            continue
        pick = None
        for v in found:
            if kind == "channel" and v.channel_id and v.channel_id not in have and ("channel", v.channel_id) not in known:
                pick = ("channel", v.channel_id, f"https://www.youtube.com/channel/{v.channel_id}", v.channel_title, v)
                break
            if kind == "video" and v.external_id not in have_items and ("video", v.external_id) not in known:
                pick = ("video", v.external_id, v.url, v.title, v)
                break
        if not pick:
            continue
        k, ext, url, title, v = pick
        with db.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO suggestions (kind, external_id, url, title, channel_title, thumb_url, duration_s, "
                "reason, for_profiles, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (k, ext, url, title or query, v.channel_title, v.thumb_url, v.duration_s if k == "video" else 0,
                 str(s.get("reason") or "")[:300], whom, time.time()),
            )
        known.add((k, ext))
        added += 1
        time.sleep(PAUSE_S)
    return f"{added} new suggestions" if added else "No new suggestions this time"
