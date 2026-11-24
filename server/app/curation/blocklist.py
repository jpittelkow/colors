"""Blocked words (ADR 0009): a match keeps a video in the inbox, even on a trusted channel."""
from __future__ import annotations

import json
import re

from ..db import Database

DEFAULT_WORDS = ["unboxing", "toy review", "prank", "scary", "horror"]


def words(db: Database) -> list[str]:
    raw = db.get_setting("blocked_words")
    if raw is None:
        return list(DEFAULT_WORDS)
    try:
        return [w for w in json.loads(raw) if isinstance(w, str) and w.strip()]
    except json.JSONDecodeError:
        return []


def set_words(db: Database, new: list[str]) -> list[str]:
    clean = sorted({w.strip().lower() for w in new if w.strip()})
    db.set_setting("blocked_words", json.dumps(clean))
    return clean


def match(text: str, blocked: list[str]) -> str:
    """The first blocked word or phrase found in text (whole words, any case), or ''."""
    low = text.lower()
    for w in blocked:
        if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", low):
            return w
    return ""
