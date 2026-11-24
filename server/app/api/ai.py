"""Settings › AI: the OpenRouter key, model and monthly cap (ADR 0034). The key is never sent back to the page."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..ai import openrouter
from ..db import Database
from .admin import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

_models_cache: dict = {"at": 0.0, "key": "", "list": []}


def _db(request: Request) -> Database:
    return request.app.state.db


@router.get("/ai")
def ai_get(request: Request) -> dict:
    db = _db(request)
    s = openrouter.settings(db)
    with db.conn() as c:
        month = c.execute("SELECT count(*), COALESCE(SUM(ok = 0), 0) FROM ai_calls WHERE ts >= ?",
                          (openrouter.month_start(),)).fetchone()
        last = c.execute("SELECT ts, purpose, ok, error FROM ai_calls ORDER BY id DESC LIMIT 1").fetchone()
        new_suggestions = c.execute("SELECT count(*) FROM suggestions WHERE status = 'new'").fetchone()[0]
    return {
        "enabled": s["enabled"], "key_saved": bool(s["key"]), "model": s["model"], "cap_usd": s["cap_usd"],
        "spent_usd": round(openrouter.spent_this_month(db), 4), "over_cap": openrouter.over_cap(db),
        "calls_this_month": month[0], "failed_this_month": month[1], "last_call": dict(last) if last else None,
        "new_suggestions": new_suggestions,
    }


class AIIn(BaseModel):
    enabled: bool | None = None
    key: str | None = Field(default=None, max_length=300)
    clear_key: bool = False
    model: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")
    cap_usd: float | None = Field(default=None, ge=0, le=1000)


@router.put("/ai")
def ai_put(body: AIIn, request: Request) -> dict:
    db = _db(request)
    if body.clear_key:
        db.set_setting("ai_key", "")
        db.set_setting("ai_enabled", "0")
    elif body.key and body.key.strip():
        key = body.key.strip()
        try:
            openrouter.check_key(key)
        except openrouter.AIError as exc:
            raise HTTPException(422, f"That key did not work. {exc}")
        db.set_setting("ai_key", key)
    if body.model:
        db.set_setting("ai_model", body.model)
    if body.cap_usd is not None:
        db.set_setting("ai_cap_usd", str(body.cap_usd))
    if body.enabled is not None:
        if body.enabled and not openrouter.settings(db)["key"]:
            raise HTTPException(422, "Save an OpenRouter key first.")
        db.set_setting("ai_enabled", "1" if body.enabled else "0")
    return ai_get(request)


@router.get("/ai/models")
def ai_models(request: Request, refresh: bool = False) -> list[dict]:
    """OpenRouter's models, loaded with the saved key (step 2 of More > AI). Cached for an hour."""
    key = openrouter.settings(_db(request))["key"]
    if not key:
        raise HTTPException(422, "Save an OpenRouter key first.")
    if refresh or _models_cache["key"] != key or time.time() - _models_cache["at"] > 3600:
        try:
            _models_cache.update(list=openrouter.models(key), at=time.time(), key=key)
        except openrouter.AIError as exc:
            raise HTTPException(502, str(exc))
    return _models_cache["list"]


@router.post("/ai/try")
def ai_try(request: Request) -> dict:
    """One tiny call, to show the key and model work."""
    try:
        out = openrouter.chat(_db(request), "test", "Answer only with JSON.", 'Reply with {"ok": true}.',
                              max_tokens=20)
    except openrouter.AIError as exc:
        raise HTTPException(502, str(exc))
    return {"ok": bool(out.get("ok"))}
