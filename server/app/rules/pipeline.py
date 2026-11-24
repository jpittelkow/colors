"""The one visibility pipeline (ADR 0022).

Every list sent to a TV and every play request goes through here. Steps run in a fixed order:
ready, approved, assigned, open (limits and closed hours), fits (time-fit, ADR 0012). Later optional rules are
added to STEPS, never around it.

A step is a SQL condition on the alias `i` (items) with named parameters. Keeping steps as SQL lets one query answer
"what can this profile see", and `explain` answers "why can't he see this?" one step at a time.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..limits import clock


@dataclass(frozen=True)
class Step:
    name: str
    reason: str  # shown to the parent when the step fails
    sql: str


# Length still to watch: the full length, minus skipped bits, minus where this profile stopped last time.
REMAINING_SQL = (
    "(i.duration_s"
    " - COALESCE((SELECT SUM(s.end_s - s.start_s) FROM segments s WHERE s.item_id = i.id), 0)"
    " - COALESCE((SELECT ws.position_s FROM watch_state ws WHERE ws.item_id = i.id"
    "   AND ws.profile_id = :profile_id AND ws.watched = 0), 0))"
)

STEPS: tuple[Step, ...] = (
    Step("ready", "The video has not finished downloading, or can't play on the TVs.", "i.status = 'ready'"),
    Step("approved", "A parent has not approved it.", "i.approval = 'approved'"),
    Step(
        "assigned",
        "It is not assigned to this profile.",
        "EXISTS (SELECT 1 FROM assignments a WHERE a.profile_id = :profile_id "
        "AND (a.item_id = i.id OR a.container_id = i.container_id))",
    ),
    Step(
        "rested",
        "Its channel is resting.",
        "NOT EXISTS (SELECT 1 FROM containers rc WHERE rc.id = i.container_id AND rc.rested_until IS NOT NULL "
        "AND rc.rested_until > date('now', 'localtime'))",
    ),
    Step("open", "The app is closed for this profile right now.", ":open = 1"),
    Step("fits", "It would not finish in the time left.", f"{REMAINING_SQL} <= :fit_s"),
)

# Columns a TV may receive. file_path, thumb_path and media_key are deliberately absent (ADR 0017, guard test).
PUBLIC_COLUMNS = "i.id, i.container_id, i.source, i.kind, i.title, i.duration_s, i.upload_date, i.added_at"

ORDERS = {
    "new": "i.added_at DESC, i.id DESC",
    "upload": "i.upload_date DESC, i.id DESC",
    "title": "i.title COLLATE NOCASE",
}


def _params(conn: sqlite3.Connection, profile_id: int, ctx: clock.Context | None) -> tuple[dict, clock.Context]:
    ctx = ctx or clock.context(conn, profile_id)
    return {"profile_id": profile_id, "open": 1 if ctx.open else 0, "fit_s": ctx.fit_s}, ctx


def _where(skip: tuple[str, ...] = ()) -> str:
    return " AND ".join(f"({s.sql})" for s in STEPS if s.name not in skip)


def visible_items(
    conn: sqlite3.Connection,
    profile_id: int,
    *,
    ctx: clock.Context | None = None,
    container_id: int | None = None,
    item_ids: list[int] | None = None,
    order: str = "new",
    limit: int = 200,
    skip: tuple[str, ...] = (),
) -> list[sqlite3.Row]:
    """Items this profile may see right now, with the resume point joined in.

    `skip` leaves out steps by name. Only three callers may use it: a video that already started may finish
    (ADR 0012), a parent's own push (ADR 0019), and building the "Picked for you" order, which skips only the
    time steps because they apply again when the row is drawn (ADR 0034).
    """
    params, _ = _params(conn, profile_id, ctx)
    sql = (
        f"SELECT {PUBLIC_COLUMNS}, c.title AS container_title, {REMAINING_SQL} AS remaining_s, "
        "COALESCE(w.position_s, 0) AS position_s, COALESCE(w.watched, 0) AS watched "
        "FROM items i JOIN containers c ON c.id = i.container_id "
        "LEFT JOIN watch_state w ON w.item_id = i.id AND w.profile_id = :profile_id "
        f"WHERE {_where(skip)}"
    )
    params["limit"] = limit
    if container_id is not None:
        sql += " AND i.container_id = :container_id"
        params["container_id"] = container_id
    if item_ids is not None:
        if not item_ids:
            return []
        marks = ",".join(str(int(x)) for x in item_ids)
        sql += f" AND i.id IN ({marks})"
    sql += f" ORDER BY {ORDERS.get(order, ORDERS['new'])} LIMIT :limit"
    return conn.execute(sql, params).fetchall()


def can_play(
    conn: sqlite3.Connection, profile_id: int, item_id: int, *, ctx: clock.Context | None = None,
    skip: tuple[str, ...] = (),
) -> bool:
    return bool(visible_items(conn, profile_id, ctx=ctx, item_ids=[item_id], limit=1, skip=skip))


def explain(conn: sqlite3.Connection, profile_id: int, item_id: int) -> list[dict]:
    """Each step and its answer for one profile and item: the parent's "why can't he see this?" check."""
    params, ctx = _params(conn, profile_id, None)
    params["item_id"] = item_id
    out = []
    for step in STEPS:
        row = conn.execute(f"SELECT 1 FROM items i WHERE i.id = :item_id AND ({step.sql})", params).fetchone()
        reason = step.reason
        if step.name == "open" and ctx.reason:
            reason = f"{reason} ({ctx.reason})"
        out.append({"step": step.name, "ok": bool(row), "reason": "" if row else reason})
    return out
