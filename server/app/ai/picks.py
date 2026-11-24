"""The "Picked for you" row: the model may only put approved, visible videos in an order (ADR 0034).

What goes in is the profile's visible list from the pipeline (ADR 0022), without the time steps, which apply again
when the row is drawn. What comes back is a list of ids; any id that was not in the input is dropped.
"""
from __future__ import annotations

import json
import time

from ..db import Database
from ..rules import pipeline
from . import openrouter, people

SYSTEM = (
    "You arrange a short row of videos for a young child, like a calm 'picked for you' shelf. You get the videos "
    "this child is allowed to watch, with ids, and what they watched lately. Choose up to 20 ids from the list and "
    "order them: mostly things like what they enjoy, some variety from other channels, unwatched before watched, "
    "no near-duplicates side by side. Use only ids from the list. Answer only with JSON: {\"order\": [ids]}."
)

MAX_CANDIDATES = 150
ROW = 20
# Steps that depend on the clock; the row is filtered by them when it is drawn, not when it is built.
TIME_STEPS = ("open", "fits")


def candidates(conn, profile_id: int) -> list:
    return pipeline.visible_items(conn, profile_id, order="new", limit=MAX_CANDIDATES, skip=TIME_STEPS)


def build(db: Database, profile_id: int, label: str) -> int:
    """Ask the model for one profile's row and cache it. Returns how many ids were kept."""
    with db.conn() as c:
        items = candidates(c, profile_id)
        recent = c.execute(
            "SELECT i.title FROM events e JOIN items i ON i.id = e.item_id WHERE e.profile_id = ? "
            "AND e.type = 'started' ORDER BY e.ts DESC LIMIT 20", (profile_id,)).fetchall()
    if not items:
        return 0
    lines = [f"{r['id']} | {r['title']} | {r['container_title']} | {round(r['duration_s'] / 60)} min"
             f"{' | watched' if r['watched'] else ''}" for r in items]
    user = (f"{label}.\nRecently started: " + ("; ".join(r["title"] for r in recent) or "nothing yet")
            + "\n\nVideos (id | title | channel | length):\n" + "\n".join(lines))
    answer = openrouter.chat(db, "picks", SYSTEM, user, max_tokens=400)
    allowed = {r["id"] for r in items}
    order = []
    for x in answer.get("order") or []:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        if i in allowed and i not in order:  # anything not offered is thrown away
            order.append(i)
    order = order[:ROW]
    with db.conn() as c:
        c.execute(
            "INSERT INTO picks (profile_id, item_ids, built_at, by_ai) VALUES (?, ?, ?, 1) "
            "ON CONFLICT (profile_id) DO UPDATE SET item_ids = excluded.item_ids, built_at = excluded.built_at, "
            "by_ai = 1", (profile_id, json.dumps(order), time.time()))
    return len(order)


def run(db: Database, job=None) -> str:
    with db.conn() as c:
        kids = [k for k in people.labels(c)
                if c.execute("SELECT picks_on FROM profiles WHERE id = ?", (k["id"],)).fetchone()[0]]
    done = []
    for k in kids:
        if job and job.stopped():
            break
        if job:
            job.note(f"Arranging {k['label']}'s row")
        done.append(build(db, k["id"], people.label_text(k)))
    return f"Rows rebuilt for {len(done)} profiles" if done else "No profiles with the row switched on"


def row(conn, db: Database, profile_id: int, visible: list) -> list:
    """The row as drawn: cached order filtered by what is visible right now, else the rule-based order."""
    on = conn.execute("SELECT picks_on FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not openrouter.is_on(db) or not on or not on[0]:
        return []
    by_id = {r["id"]: r for r in visible}
    got = conn.execute("SELECT item_ids FROM picks WHERE profile_id = ?", (profile_id,)).fetchone()
    picked = []
    if got:
        try:
            picked = [by_id[i] for i in json.loads(got["item_ids"]) if i in by_id]
        except (ValueError, TypeError):
            picked = []
    if len(picked) >= 4:
        return picked
    # Fallback (ADR 0034): the rule-based "Up next" order, unwatched first.
    return sorted(visible, key=lambda r: r["watched"])[:ROW]
