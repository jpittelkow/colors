"""OpenRouter's chat API, the AI settings and the monthly spending cap (ADR 0034).

The key lives in the settings table and never leaves the server: the page only learns whether one is saved.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ..db import Database

API = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
DEFAULT_CAP_USD = 2.0


class AIError(Exception):
    pass


def settings(db: Database) -> dict:
    return {
        "enabled": db.get_setting("ai_enabled") == "1",
        "key": db.get_setting("ai_key") or "",
        "model": db.get_setting("ai_model") or DEFAULT_MODEL,
        "cap_usd": float(db.get_setting("ai_cap_usd") or DEFAULT_CAP_USD),
    }


def is_on(db: Database) -> bool:
    s = settings(db)
    return s["enabled"] and bool(s["key"])


def month_start(now: float | None = None) -> float:
    t = time.localtime(time.time() if now is None else now)
    return time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1))


def spent_this_month(db: Database, now: float | None = None) -> float:
    with db.conn() as c:
        return float(c.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM ai_calls WHERE ts >= ?",
                               (month_start(now),)).fetchone()[0])


def over_cap(db: Database) -> bool:
    return spent_this_month(db) >= settings(db)["cap_usd"]


def _http(method: str, url: str, key: str, body: dict | None = None, timeout: float = 60) -> dict:
    """One HTTP call to OpenRouter. Tests replace this function."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "kidtube",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise AIError(f"OpenRouter said {exc.code}: {msg or exc.reason}") from None
    except urllib.error.URLError as exc:
        raise AIError(f"Could not reach OpenRouter: {exc.reason}") from None


def chat(db: Database, purpose: str, system: str, user: str, *, max_tokens: int = 1500) -> dict:
    """Ask the model for a JSON object. Records the call and its price. Raises AIError."""
    s = settings(db)
    if not s["key"]:
        raise AIError("No OpenRouter key saved.")
    if over_cap(db):
        raise AIError("This month's AI spending cap is reached.")
    body = {
        "model": s["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "usage": {"include": True},
    }
    ok, error, usage, content = 1, "", {}, ""
    try:
        res = _http("POST", f"{API}/chat/completions", s["key"], body)
        if res.get("error"):
            raise AIError(str(res["error"].get("message") or res["error"]))
        usage = res.get("usage") or {}
        content = ((res.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except AIError as exc:
        ok, error = 0, str(exc)
        raise
    finally:
        with db.conn() as c:
            c.execute(
                "INSERT INTO ai_calls (ts, purpose, model, tokens_in, tokens_out, cost_usd, ok, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), purpose, s["model"], int(usage.get("prompt_tokens") or 0),
                 int(usage.get("completion_tokens") or 0), float(usage.get("cost") or 0), ok, error[:300]),
            )
    return parse_json(content)


def parse_json(text: str) -> dict:
    """The model's answer as a dict. Tolerates a ```json fence around it."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    try:
        out = json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start < 0 or end <= start:
            raise AIError("The model did not answer in JSON.") from None
        try:
            out = json.loads(t[start:end + 1])
        except json.JSONDecodeError:
            raise AIError("The model did not answer in JSON.") from None
    if not isinstance(out, dict):
        raise AIError("The model did not answer with an object.")
    return out


def models(key: str) -> list[dict]:
    """Text models on OpenRouter, cheapest first, with price per million tokens."""
    res = _http("GET", f"{API}/models", key, timeout=20)
    out = []
    for m in res.get("data") or []:
        p = m.get("pricing") or {}
        try:
            pin, pout = float(p.get("prompt") or 0) * 1e6, float(p.get("completion") or 0) * 1e6
        except (TypeError, ValueError):
            continue
        mods = (m.get("architecture") or {}).get("output_modalities") or ["text"]
        if set(mods) != {"text"} or pin < 0:  # chat models only: no image, audio or music output
            continue
        out.append({"id": m.get("id"), "name": m.get("name") or m.get("id"), "in_per_m": round(pin, 3),
                    "out_per_m": round(pout, 3), "context": int(m.get("context_length") or 0),
                    "free": pin == 0 and pout == 0})
    out.sort(key=lambda m: (m["in_per_m"] + m["out_per_m"], m["name"]))
    return out


def check_key(key: str) -> dict:
    """Is this key good? OpenRouter's key endpoint answers with its limits."""
    res = _http("GET", f"{API}/key", key, timeout=20)
    return res.get("data") or {}
