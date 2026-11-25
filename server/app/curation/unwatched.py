"""Channels nobody watches (ADR 0042): a list for the parents' page that suggests, never acts.

A child "hasn't watched" a channel when he has started nothing from it for `unwatched_days` (30 by default). Only
channels he could actually reach count: assigned to him, not resting, with at least one ready, approved video. The
clock starts at his last play, or when the channel came into colors if he never played it, so a new channel is not
"unloved". Everything is read from the local event log (ADR 0021); nothing leaves the house.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..db import Database

DEFAULT_DAYS = 30
KEEP_DAYS = 90  # "Keep it" hides a channel from the list this long
DAY_S = 86400


def days_setting(db: Database) -> int:
    try:
        return max(1, min(365, int(db.get_setting("unwatched_days", str(DEFAULT_DAYS)))))
    except (TypeError, ValueError):
        return DEFAULT_DAYS


def keep(db: Database, container_id: int, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with db.conn() as c:
        return c.execute("UPDATE containers SET kept_until = ? WHERE id = ?",
                         (now + KEEP_DAYS * DAY_S, container_id)).rowcount > 0


def _bytes(library_dir: Path, paths: list[str]) -> int:
    total = 0
    for p in paths:
        try:
            total += (library_dir / p).stat().st_size
        except OSError:
            pass
    return total


def report(db: Database, library_dir: Path, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    days = days_setting(db)
    line = now - days * DAY_S
    with db.conn() as c:
        kids = {r["id"]: dict(r) for r in c.execute(
            "SELECT id, name, avatar, avatar_color FROM profiles WHERE kind = 'child' ORDER BY position, id")}
        if not kids:
            return {"days": days, "channels": [], "empty": []}
        # Who is assigned what, by channel: a whole channel, or single videos from it.
        assigned: dict[int, set[int]] = {}
        for r in c.execute(
                "SELECT DISTINCT a.profile_id, COALESCE(a.container_id, i.container_id) AS cid FROM assignments a "
                "LEFT JOIN items i ON i.id = a.item_id"):
            if r["profile_id"] in kids and r["cid"] is not None:
                assigned.setdefault(r["cid"], set()).add(r["profile_id"])
        # What each child can play from each channel, and how much of it he has finished.
        reach = {(r["profile_id"], r["cid"]): dict(r) for r in c.execute(
            "SELECT a.profile_id, i.container_id AS cid, count(DISTINCT i.id) AS n, min(i.duration_s) AS shortest_s, "
            "count(DISTINCT CASE WHEN EXISTS (SELECT 1 FROM watch_state ws WHERE ws.profile_id = a.profile_id "
            "  AND ws.item_id = i.id AND ws.watched = 1) THEN i.id END) AS finished "
            "FROM assignments a JOIN items i ON (i.container_id = a.container_id OR i.id = a.item_id) "
            "WHERE i.status = 'ready' AND i.approval = 'approved' GROUP BY a.profile_id, i.container_id")}
        # His newest play per channel: a start or a finish in the log, or a resume point.
        last: dict[tuple[int, int], float] = {}
        for r in c.execute(
                "SELECT e.profile_id, i.container_id AS cid, max(e.ts) AS ts FROM events e JOIN items i ON i.id = e.item_id "
                "WHERE e.type IN ('started', 'finished') AND e.profile_id IS NOT NULL GROUP BY e.profile_id, i.container_id "
                "UNION ALL SELECT ws.profile_id, i.container_id, max(ws.updated_at) FROM watch_state ws "
                "JOIN items i ON i.id = ws.item_id GROUP BY ws.profile_id, i.container_id"):
            k = (r["profile_id"], r["cid"])
            last[k] = max(last.get(k, 0), r["ts"] or 0)
        limits = {r["profile_id"]: dict(r) for r in c.execute(
            "SELECT profile_id, weekday_min, weekend_min, timefit FROM limits")}
        chans = {r["id"]: dict(r) for r in c.execute(
            "SELECT c.id, c.source, c.external_id, c.title, c.thumb_url, c.added_at, c.kept_until, "
            "s.id AS sub_id, s.active AS sub_active FROM containers c LEFT JOIN subscriptions s ON s.container_id = c.id "
            "WHERE c.rested_until IS NULL OR c.rested_until <= date('now', 'localtime')")}
        counts = {r["cid"]: dict(r) for r in c.execute(
            "SELECT container_id AS cid, sum(status = 'failed') AS failed, sum(status = 'pending') AS pending, "
            "sum(approval = 'waiting' AND status <> 'failed') AS waiting FROM items GROUP BY container_id")}

    def daily_limit_min(pid: int) -> int | None:
        lim = limits.get(pid)
        if not lim or not lim["timefit"] or lim["weekday_min"] is None or lim["weekend_min"] is None:
            return None
        return max(lim["weekday_min"], lim["weekend_min"])

    out, empty = [], []
    for cid, pids in assigned.items():
        ch = chans.get(cid)
        if ch is None or (ch["kept_until"] or 0) > now:
            continue
        rows = []
        for pid in sorted(pids, key=lambda p: list(kids).index(p)):
            got = reach.get((pid, cid))
            if not got:
                continue
            ts = last.get((pid, cid))
            start = ts or ch["added_at"]
            stale = start < line
            reason = None
            if stale and got["finished"] >= got["n"]:
                reason = {"kind": "finished", "videos": got["n"]}
            elif stale and (lim := daily_limit_min(pid)) is not None and (got["shortest_s"] or 0) > lim * 60:
                reason = {"kind": "too_long", "limit_min": lim, "shortest_min": round(got["shortest_s"] / 60)}
            rows.append({
                "profile_id": pid, "last_played": ts, "days": int((now - start) // DAY_S), "never": ts is None,
                "stale": stale, "videos": got["n"], "reason": reason,
            })
        base = {"id": cid, "source": ch["source"], "external_id": ch["external_id"], "title": ch["title"],
                "thumb_url": ch["thumb_url"], "sub_id": ch["sub_id"], "sub_active": bool(ch["sub_active"])}
        if not rows:
            # Assigned, but nothing to play: about downloads or approval, not the boys. New ones are left alone.
            if ch["added_at"] < line:
                n = counts.get(cid) or {}
                empty.append({**base, "profile_ids": sorted(pids, key=lambda p: list(kids).index(p)),
                              "failed": n.get("failed") or 0, "pending": n.get("pending") or 0,
                              "waiting": n.get("waiting") or 0})
            continue
        stale_rows = [r for r in rows if r["stale"]]
        if not stale_rows:
            continue
        top = max(stale_rows, key=lambda r: r["days"])
        out.append({**base, "kids": rows, "days": top["days"], "never": top["never"], "videos": max(r["videos"] for r in rows)})

    if out:  # size on disk and what came in since anyone last watched, for the listed channels only
        ids = [ch["id"] for ch in out]
        q = ",".join("?" * len(ids))
        with db.conn() as c:
            files: dict[int, list[str]] = {}
            for r in c.execute(f"SELECT container_id, file_path FROM items WHERE container_id IN ({q}) AND file_path != ''", ids):
                files.setdefault(r["container_id"], []).append(r["file_path"])
            added = [(r["container_id"], r["added_at"]) for r in c.execute(
                f"SELECT container_id, added_at FROM items WHERE container_id IN ({q}) AND status = 'ready'", ids)]
        for ch in out:
            ch["bytes"] = _bytes(library_dir, files.get(ch["id"], []))
            seen = max((r["last_played"] or 0 for r in ch["kids"]), default=0)
            ch["new_since"] = sum(1 for cid, t in added if cid == ch["id"] and t > seen) if ch["sub_id"] and seen else 0
    out.sort(key=lambda ch: (-ch["days"], ch["title"].lower()))
    empty.sort(key=lambda ch: ch["title"].lower())
    return {"days": days, "channels": out, "empty": empty}
