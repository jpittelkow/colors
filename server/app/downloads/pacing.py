"""Backing off when YouTube says we are asking too much (2026-11-24).

On 2026-11-24 the 6-hourly retry put 287 failed downloads back at once, the queue ran them back to back, and YouTube
answered "Sign in to confirm you're not a bot" for every one: 377 downloads failed in two hours, each tried three
times, which only kept the block going.

So an answer like that is not a failure of that video. The download goes back in the queue without using up a try,
and the whole queue takes a break. A second block soon after the first means a longer break. The first download
that works again ends the streak. The break shows on the parents' page (activity), and a parent can end it.
"""
from __future__ import annotations

import time

from ..db import Database

# What YouTube says when it has had enough of this address (yt-dlp's wording).
BLOCK_MARKERS = ("confirm you’re not a bot", "confirm you're not a bot", "http error 429", "too many requests")
BREAKS_S: tuple[float, ...] = (3600, 3 * 3600, 6 * 3600)  # first block, second within a day, then
STREAK_S = 24 * 3600  # a block more than this long after the last one starts the streak again
BETWEEN_S = 15.0  # between downloads, so a long queue is not one long burst

UNTIL, COUNT, AT = "yt_blocked_until", "yt_block_count", "yt_block_at"


def is_block(error: object) -> bool:
    e = str(error).lower()
    return any(m in e for m in BLOCK_MARKERS)


def blocked_until(db: Database, now: float | None = None) -> float:
    """When the break ends (0 when there is none)."""
    until = float(db.get_setting(UNTIL) or 0)
    return until if until > (time.time() if now is None else now) else 0.0


def note_block(db: Database, now: float | None = None) -> float:
    """YouTube said "not a bot": start (or keep) a break, longer for each block in a row. Returns when it ends."""
    now = time.time() if now is None else now
    if blocked_until(db, now):
        return float(db.get_setting(UNTIL))  # already on a break: the downloads in flight don't stretch it
    last = float(db.get_setting(AT) or 0)
    count = int(db.get_setting(COUNT) or 0) + 1 if now - last < STREAK_S else 1
    until = now + BREAKS_S[min(count, len(BREAKS_S)) - 1]
    db.set_setting(COUNT, str(count))
    db.set_setting(AT, str(now))
    db.set_setting(UNTIL, str(until))
    return until


def note_success(db: Database) -> None:
    """A download worked: the streak of blocks is over."""
    if db.get_setting(COUNT) not in (None, "", "0"):
        db.set_setting(COUNT, "0")


def end_break(db: Database) -> None:
    """A parent says go on now."""
    db.set_setting(UNTIL, "0")


def status(db: Database, now: float | None = None) -> dict | None:
    """For the activity pill: the break, if there is one."""
    until = blocked_until(db, now)
    return {"until": until, "blocks": int(db.get_setting(COUNT) or 0)} if until else None
