"""Passwords, device tokens and signed tokens (ADR 0006, ADR 0018)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .db import Database


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def check_password(password: str, stored: str) -> bool:
    try:
        salt_b64, digest_b64 = stored.split("$", 1)
        salt, want = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
    except ValueError:
        return False
    got = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(got, want)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_pair_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class Signer:
    """HMAC-signed, expiring tokens. The key is made on first run and kept in the settings table."""

    def __init__(self, db: Database):
        key = db.get_setting("secret_key")
        if not key:
            key = secrets.token_hex(32)
            db.set_setting("secret_key", key)
        self._key = bytes.fromhex(key)

    def sign(self, payload: dict, ttl_s: float) -> str:
        body = dict(payload, exp=time.time() + ttl_s)
        raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).rstrip(b"=")
        mac = base64.urlsafe_b64encode(hmac.new(self._key, raw, hashlib.sha256).digest()).rstrip(b"=")
        return (raw + b"." + mac).decode()

    def read(self, token: str, *, allow_expired: bool = False) -> dict | None:
        """Return the payload, or None if the token is forged or (unless allowed) expired."""
        try:
            raw, mac = token.encode().split(b".", 1)
            want = base64.urlsafe_b64encode(hmac.new(self._key, raw, hashlib.sha256).digest()).rstrip(b"=")
            if not hmac.compare_digest(mac, want):
                return None
            body = json.loads(base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4)))
        except (ValueError, json.JSONDecodeError):
            return None
        body["expired"] = body.get("exp", 0) < time.time()
        if body["expired"] and not allow_expired:
            return None
        return body
