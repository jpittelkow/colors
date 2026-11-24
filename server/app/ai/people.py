"""How the boys are described to the model: "Child A" with an age band, never a name or birthday (ADR 0034)."""
from __future__ import annotations

import datetime as dt
import string


def age_band(birthday: str | None, today: dt.date | None = None) -> str:
    if not birthday:
        return ""
    try:
        born = dt.date.fromisoformat(birthday[:10])
    except ValueError:
        return ""
    today = today or dt.date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if years < 3:
        return "under 3"
    if years < 6:
        return "3 to 5"
    if years < 9:
        return "6 to 8"
    return "9 or older"


def labels(conn) -> list[dict]:
    """Child profiles in order, each with the label the model sees."""
    rows = conn.execute(
        "SELECT id, birthday FROM profiles WHERE kind = 'child' ORDER BY position, id").fetchall()
    out = []
    for n, r in enumerate(rows):
        letter = string.ascii_uppercase[n] if n < 26 else str(n)
        out.append({"id": r["id"], "label": f"Child {letter}", "age": age_band(r["birthday"])})
    return out


def label_text(p: dict) -> str:
    return p["label"] + (f" (age {p['age']})" if p["age"] else "")
