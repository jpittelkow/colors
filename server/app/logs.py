"""Logging: to the console (docker logs) and to <data>/logs/colors.log.

A new file every few days, the last few kept, so there is about a fortnight to look back on and the folder never
grows. Every failed request is written down with why it failed (a 422 used to leave nothing but its status code),
and so are slow requests and crashes. Paths only, never query strings, with a stream link's signed token masked
(`safe_path`), and never the values a rejected request carried (one can be a password).
"""
from __future__ import annotations

import logging
import re
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ROTATE_DAYS = 3  # a new file every 3 days
KEEP = 3         # and the 3 before it: about 12 days in all
SLOW_S = 5.0
FMT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

log = logging.getLogger("kidtube.http")

_TOKEN_PATH = re.compile(r"/stream/[^/?]+")


def safe_path(path: str) -> str:
    """A request path fit for the log: no query string, and a stream link's signed token masked."""
    return _TOKEN_PATH.sub("/stream/<token>", str(path).split("?", 1)[0])

# The names a parent sees on the page, for "Check “Most downloads a day”: ..." instead of a field name.
LABELS = {
    "url": "Link", "last_n": "How many of the latest", "min_s": "Shortest video", "max_s": "Longest video",
    "check_hours": "Check every (hours)", "daily_cap": "Most downloads a day", "keep_n": "How many to keep",
    "keep_days": "Days after watching", "title_must": "Title must have", "title_not": "Title must not have",
    "minutes": "Minutes", "password": "Password", "name": "Name",
}


class _QuietAccess(logging.Filter):
    """Into the file: changes (anything but GET) and failures. The page asks for news every few seconds, and
    those GETs would bury everything else."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) >= 5:
            method, status = args[1], args[4]
            record.args = (args[0], method, safe_path(args[2]), *args[3:])  # no tokens, no query strings
            try:
                return method != "GET" or int(status) >= 400
            except (TypeError, ValueError):
                return True
        return True


def setup(data_dir: Path) -> Path:
    """Send everything to the console and the rotating file. Safe to call twice. Returns the file's path."""
    folder = data_dir / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "colors.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(getattr(h, "colors_file", False) for h in root.handlers):
        return path
    fmt = logging.Formatter(FMT)
    fh = TimedRotatingFileHandler(path, when="D", interval=ROTATE_DAYS, backupCount=KEEP, encoding="utf-8")
    fh.colors_file = True
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if not any(type(h) is logging.StreamHandler for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    # uvicorn's own loggers do not pass their lines on to the root logger, so give them files directly: its
    # errors into colors.log, and requests (only changes and failures) into access.log beside it.
    logging.getLogger("uvicorn.error").addHandler(fh)
    acc_fh = TimedRotatingFileHandler(folder / "access.log", when="D", interval=ROTATE_DAYS, backupCount=KEEP,
                                      encoding="utf-8")
    acc_fh.setFormatter(fmt)
    acc_fh.addFilter(_QuietAccess())
    logging.getLogger("uvicorn.access").addHandler(acc_fh)
    logging.getLogger("kidtube").info("logging to %s (a new file every %d days, %d kept)", path, ROTATE_DAYS, KEEP)
    return path


def install(app: FastAPI) -> None:
    """Write down every failed request with its reason, slow requests, and crashes."""

    @app.exception_handler(RequestValidationError)
    async def bad_values(request: Request, exc: RequestValidationError):
        errs = jsonable_encoder(exc.errors())
        for e in errs:
            e.pop("input", None)  # never echo or log what was typed: it can be a password
            e.pop("ctx", None)
        brief = [(".".join(str(x) for x in e.get("loc", [])[1:]), e.get("msg")) for e in errs[:5]]
        log.warning("422 %s %s: %s", request.method, safe_path(request.url.path), brief)
        first = errs[0] if errs else {}
        field = str((first.get("loc") or [""])[-1])
        label = LABELS.get(field, field.replace("_", " "))
        msg = (first.get("msg") or "not a valid value").rstrip(".")
        return JSONResponse(status_code=422, content={"detail": {"message": f"Check “{label}”: {msg}.", "errors": errs}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            log.error("%s %s %s: %s", exc.status_code, request.method, safe_path(request.url.path), exc.detail)
        elif exc.status_code not in (401, 404):  # signed out / missing thumbnails: too common to be news
            log.warning("%s %s %s: %s", exc.status_code, request.method, safe_path(request.url.path), exc.detail)
        return await http_exception_handler(request, exc)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("500 %s %s crashed", request.method, safe_path(request.url.path))
            raise
        took = time.monotonic() - start
        if took > SLOW_S:
            log.warning("slow: %s %s took %.1fs (%s)", request.method, safe_path(request.url.path), took, response.status_code)
        return response
