"""Time limits, kept on the server (ADR 0011), and the numbers time-fit needs (ADR 0012).

Two kinds of time:
- watched time (daily allowance, session) only counts while a video plays;
- wall-clock time (a one-off limit, closed hours, a parent's lock) runs regardless.

`context()` answers, for one profile right now: is the app open, how much time is left, and how long a video
may be and still fit. Everything that lists or plays videos for a child asks it first.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

ROLLOVER_HOUR = 4          # a new day starts at 04:00 local time
HARD_CAP_S = 10 * 60       # a video that fitted may overrun its limit by at most this much
HEARTBEAT_MAX_GAP_S = 45   # a longer gap between heartbeats is not counted as watching
PLAYING_FRESH_S = 60       # a TV whose last heartbeat is older than this is not playing any more
NO_LIMIT = 1e12


def day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now - ROLLOVER_HOUR * 3600))


def day_end(now: float) -> float:
    """The moment the current day rolls over."""
    lt = time.localtime(now - ROLLOVER_HOUR * 3600)
    start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) + ROLLOVER_HOUR * 3600
    return start + 24 * 3600


def _minutes_of_day(now: float) -> int:
    lt = time.localtime(now)
    return lt.tm_hour * 60 + lt.tm_min


def _hhmm(s: str | None) -> int | None:
    if not s:
        return None
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


@dataclass
class Context:
    profile_id: int
    open: bool = True
    reason: str = ""                 # why closed, or which limit is the tightest
    limited: bool = False
    left_s: float | None = None      # None = no limit running
    over_s: float = 0                # how far past the limit point we are (for the hard cap)
    fit_s: float = NO_LIMIT          # longest remaining length that may be shown
    used_today_s: float = 0
    daily_s: float | None = None     # today's allowance including extra minutes
    timefit: bool = True
    show_timer: bool = True
    grace_s: float = 120
    autoplay_n: int = 2
    lastone: bool = False
    # The one video "last one" allows, once chosen: the one playing when a parent pressed it, else the next one
    # started. Kept in the override's note as "item:<id>".
    lastone_item: int | None = None
    opens_at: str = ""               # closed hours: the time they end, for the TV's "Good night" screen
    hard_stop: bool = False          # a parent ended it: stop even mid-video
    limits: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "open": self.open,
            "reason": self.reason,
            "limited": self.limited,
            "left_s": None if self.left_s is None else max(0, round(self.left_s)),
            "used_today_s": round(self.used_today_s),
            "daily_s": self.daily_s,
            "show_timer": self.show_timer,
            "lastone": self.lastone,
            "opens_at": self.opens_at if self.reason == "Closed now" else "",
        }


def get_limits(conn: sqlite3.Connection, profile_id: int) -> dict:
    row = conn.execute("SELECT * FROM limits WHERE profile_id = ?", (profile_id,)).fetchone()
    if row:
        return dict(row)
    return {
        "profile_id": profile_id, "weekday_min": None, "weekend_min": None, "session_min": None, "break_min": 60,
        "closed_from": None, "closed_to": None, "timefit": 1, "grace_min": 2, "show_timer": 1, "autoplay_n": 2,
    }


def context(conn: sqlite3.Connection, profile_id: int, now: float | None = None) -> Context:
    now = time.time() if now is None else now
    lim = get_limits(conn, profile_id)
    day = day_key(now)
    ctx = Context(
        profile_id=profile_id, timefit=bool(lim["timefit"]), show_timer=bool(lim["show_timer"]),
        grace_s=(lim["grace_min"] or 0) * 60, autoplay_n=lim["autoplay_n"], limits=lim,
    )
    row = conn.execute("SELECT seconds FROM watch_time WHERE profile_id = ? AND day = ?", (profile_id, day)).fetchone()
    ctx.used_today_s = row["seconds"] if row else 0
    ovr = conn.execute(
        "SELECT * FROM overrides WHERE profile_id = ? AND day = ? AND done = 0 ORDER BY id", (profile_id, day)
    ).fetchall()

    candidates: list[tuple[float, str, float]] = []  # (left_s, reason, over_s)

    # Daily allowance (watched time), plus any extra minutes a parent gave today.
    # Vacation mode (set from the page or Home Assistant) uses the weekend allowance every day.
    vac = conn.execute("SELECT value FROM settings WHERE key = 'vacation_mode'").fetchone()
    weekend = time.localtime(now - ROLLOVER_HOUR * 3600).tm_wday >= 5 or bool(vac and vac["value"] == "1")
    cap_min = lim["weekend_min"] if weekend else lim["weekday_min"]
    extra_s = sum(o["minutes"] * 60 for o in ovr if o["kind"] == "extra")
    if cap_min is not None:
        ctx.daily_s = cap_min * 60 + extra_s
        left = ctx.daily_s - ctx.used_today_s
        candidates.append((left, "Daily time used up" if left <= 0 else "Daily time", max(0, -left)))

    # One sitting (watched time), then a break.
    if lim["session_min"]:
        s = conn.execute("SELECT * FROM sessions WHERE profile_id = ?", (profile_id,)).fetchone()
        if s and now - s["last_at"] < lim["break_min"] * 60:
            left = lim["session_min"] * 60 + extra_s - s["seconds"]
            if left <= 0:
                # The break runs from the last moment of watching.
                candidates.append((left, "Break time", max(0, -left)))
            else:
                candidates.append((left, "This sitting", 0))

    # A one-off limit started by a parent (wall clock).
    for o in ovr:
        if o["kind"] == "oneoff" and o["ends_at"]:
            left = o["ends_at"] - now
            candidates.append((left, "Time's up" if left <= 0 else "Time limit", max(0, -left)))

    # Closed hours (wall clock).
    cf, ct = _hhmm(lim["closed_from"]), _hhmm(lim["closed_to"])
    unlocked = any(o["kind"] == "unlock" and (o["ends_at"] or 0) > now for o in ovr)
    if cf is not None and ct is not None and cf != ct and not unlocked:
        m = _minutes_of_day(now)
        inside = (cf <= m < ct) if cf < ct else (m >= cf or m < ct)
        if inside:
            ctx.opens_at = lim["closed_to"] or ""
            over = ((m - cf) % (24 * 60)) * 60
            candidates.append((-over, "Closed now", over))
        else:
            until_close = ((cf - m) % (24 * 60)) * 60
            candidates.append((until_close, "Until closing time", 0))

    # A parent pressed "end now".
    for o in ovr:
        if o["kind"] == "lock" and (o["ends_at"] is None or o["ends_at"] > now) and not unlocked:
            ctx.open, ctx.reason, ctx.hard_stop = False, "Stopped by a parent", True
            ctx.left_s, ctx.limited = 0, True
            return ctx

    ctx.lastone = any(o["kind"] == "lastone" for o in ovr)
    for o in ovr:
        if o["kind"] == "lastone" and o["note"].startswith("item:"):
            ctx.lastone_item = int(o["note"][5:])

    if candidates:
        left, reason, over = min(candidates, key=lambda c: c[0])
        ctx.limited = True
        ctx.left_s, ctx.reason, ctx.over_s = left, reason, over
        if left <= 0:
            ctx.open = False
        ctx.fit_s = (max(0.0, left) + ctx.grace_s) if ctx.timefit else NO_LIMIT
    return ctx


def count_heartbeat(conn: sqlite3.Connection, device: sqlite3.Row, profile_id: int, state: str, now: float) -> float:
    """Add the time since this device's last heartbeat to the profile's day and session. Returns seconds added."""
    gap = now - (device["last_heartbeat"] or 0)
    counted = 0.0
    if (
        state in ("playing", "ended")
        and device["last_state"] == "playing"
        and device["last_profile_id"] == profile_id
        and 0 < gap <= HEARTBEAT_MAX_GAP_S
    ):
        counted = gap
    if counted:
        day = day_key(now)
        conn.execute(
            "INSERT INTO watch_time (profile_id, day, seconds) VALUES (?, ?, ?) "
            "ON CONFLICT (profile_id, day) DO UPDATE SET seconds = seconds + excluded.seconds",
            (profile_id, day, counted),
        )
        lim = get_limits(conn, profile_id)
        s = conn.execute("SELECT * FROM sessions WHERE profile_id = ?", (profile_id,)).fetchone()
        if s and now - s["last_at"] < (lim["break_min"] or 0) * 60 + gap:
            conn.execute(
                "UPDATE sessions SET last_at = ?, seconds = seconds + ? WHERE profile_id = ?", (now, counted, profile_id)
            )
        else:
            conn.execute(
                "INSERT INTO sessions (profile_id, started_at, last_at, seconds) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (profile_id) DO UPDATE SET started_at = excluded.started_at, last_at = excluded.last_at, "
                "seconds = excluded.seconds",
                (profile_id, now - counted, now, counted),
            )
    return counted


def add_override(conn: sqlite3.Connection, profile_id: int, kind: str, *, minutes: float = 0, now: float | None = None,
                 note: str = "") -> int:
    now = time.time() if now is None else now
    day = day_key(now)
    ends_at = None
    if kind == "oneoff":
        conn.execute(
            "UPDATE overrides SET done = 1 WHERE profile_id = ? AND day = ? AND kind = 'oneoff'", (profile_id, day)
        )
        ends_at = now + minutes * 60
    elif kind == "lock":
        ends_at = day_end(now)
        conn.execute("UPDATE overrides SET done = 1 WHERE profile_id = ? AND kind IN ('unlock', 'lastone')", (profile_id,))
    elif kind == "unlock":
        ends_at = now + (minutes or 60) * 60
        conn.execute("UPDATE overrides SET done = 1 WHERE profile_id = ? AND kind = 'lock'", (profile_id,))
    return conn.execute(
        "INSERT INTO overrides (profile_id, kind, day, minutes, starts_at, ends_at, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile_id, kind, day, minutes, now, ends_at, note),
    ).lastrowid


ACTIONS = ("extra", "limit", "clear-limit", "lastone", "lock", "unlock")


def apply_action(conn: sqlite3.Connection, profile_id: int, action: str, minutes: float = 0) -> None:
    """A parent's action from the page or from Home Assistant (ADR 0011, ADR 0020)."""
    if action == "extra":
        add_override(conn, profile_id, "extra", minutes=minutes or 10)
    elif action == "limit":
        add_override(conn, profile_id, "oneoff", minutes=minutes or 30)
    elif action == "clear-limit":
        clear_today(conn, profile_id, ("oneoff",))
    elif action == "lastone":
        oid = add_override(conn, profile_id, "lastone")
        # Watching right now: this video is the last one. Otherwise the next one started is.
        playing = conn.execute(
            "SELECT last_item_id FROM devices WHERE last_profile_id = ? AND last_state IN ('playing', 'starting') "
            "AND last_heartbeat > ? AND revoked = 0 ORDER BY last_heartbeat DESC LIMIT 1",
            (profile_id, time.time() - PLAYING_FRESH_S),
        ).fetchone()
        if playing and playing[0]:
            conn.execute("UPDATE overrides SET note = ? WHERE id = ?", (f"item:{playing[0]}", oid))
    elif action == "lock":
        add_override(conn, profile_id, "lock")
    elif action == "unlock":
        add_override(conn, profile_id, "unlock", minutes=minutes or 60)
    else:
        raise ValueError(f"Unknown action {action!r}.")


def claim_lastone(conn: sqlite3.Connection, profile_id: int, item_id: int) -> bool:
    """The first video started after "last one" becomes the last one. True if `item_id` is now the last one.

    Two TVs starting different videos at the same moment: only one UPDATE finds the note still empty, and the
    other reads back whichever video won.
    """
    conn.execute(
        "UPDATE overrides SET note = ? WHERE profile_id = ? AND kind = 'lastone' AND done = 0 AND note = ''",
        (f"item:{item_id}", profile_id),
    )
    row = conn.execute(
        "SELECT note FROM overrides WHERE profile_id = ? AND kind = 'lastone' AND done = 0 ORDER BY id DESC LIMIT 1",
        (profile_id,),
    ).fetchone()
    return row is None or row["note"] == f"item:{item_id}"


def clear_today(conn: sqlite3.Connection, profile_id: int, kinds: tuple[str, ...], now: float | None = None) -> None:
    now = time.time() if now is None else now
    marks = ",".join("?" for _ in kinds)
    conn.execute(
        f"UPDATE overrides SET done = 1 WHERE profile_id = ? AND day = ? AND kind IN ({marks})",
        (profile_id, day_key(now), *kinds),
    )
