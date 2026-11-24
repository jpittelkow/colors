"""One process: the admin API and page, the TV API, streaming and the download worker (ADR 0003)."""
from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import background
from .api import admin, ai, automation, downloads, extras, manage, tv
from .channel_pics import ChannelPics
from .config import Config
from .db import Database, migrate
from .downloads.jobs import Worker
from .downloads.ytdlp import YtDlp
from .jobs_registry import Registry
from .security import Signer, hash_password

STATIC_DIR = Path(__file__).parent / "static"


class FreshStaticFiles(StaticFiles):
    """The parents' page: the browser checks back every load (a cheap 304 when nothing changed), so a deploy shows at
    once. Without a Cache-Control header browsers guessed, and kept running yesterday's app.js after an update."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(cfg: Config | None = None, downloader=None) -> FastAPI:
    cfg = cfg or Config.from_env()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.library_dir.mkdir(parents=True, exist_ok=True)
    migrate(cfg.db_path, cfg.migrations_dir)
    db = Database(cfg.db_path)
    first_password = os.environ.get("KIDTUBE_ADMIN_PASSWORD", "")
    if first_password and db.get_setting("admin_password") is None and len(first_password) >= 6:
        db.set_setting("admin_password", hash_password(first_password))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        threads = []
        if cfg.run_worker:
            threads = [Worker(db, app.state.downloader, cfg.library_dir), app.state.registry]
            for t in threads:
                t.start()
        yield
        for t in threads:
            t.stop()

    app = FastAPI(title="colors", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.cfg = cfg
    app.state.db = db
    app.state.signer = Signer(db)
    app.state.downloader = downloader or YtDlp(cfg.library_dir, cfg.data_dir / "cookies.txt", cfg.ffmpeg_dir)
    app.state.pics = ChannelPics(db, app.state.downloader, cfg.data_dir)
    app.state.registry = Registry(db, app.state, background.all_jobs())

    app.include_router(admin.router)
    app.include_router(manage.router)
    app.include_router(automation.router)
    app.include_router(automation.admin_router)
    app.include_router(extras.router)
    app.include_router(downloads.router)
    app.include_router(ai.router)
    app.include_router(tv.router)

    @app.get("/healthz")
    def healthz() -> dict:
        with db.conn() as c:
            c.execute("SELECT 1").fetchone()
        return {"ok": True}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse("/admin/")

    @app.get("/avatars/custom/{name}")
    def custom_avatar(name: str, request: Request) -> FileResponse:
        """A parent-uploaded profile picture: for the parents' page or a paired TV only (ADR 0036)."""
        if not admin._authed(request):
            row = tv._device_row(request)  # 401 without a TV token
            if row["paired_at"] is None:
                raise HTTPException(403)
        if not re.fullmatch(r"\d+-[0-9a-f]{16}\.(png|jpg|webp|gif)", name):
            raise HTTPException(404)
        f = cfg.data_dir / "avatars" / name
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, headers={"Cache-Control": "private, max-age=604800"})

    extras.EXTRA_AVATAR_DIR = cfg.data_dir / "characters"

    @app.get("/avatars/{name}.svg")
    def character(name: str) -> FileResponse:
        """A character picture, the household's own (data dir) or built in. No scripts run in an SVG opened alone."""
        f = extras.avatar_file(name)
        if not f:
            raise HTTPException(404)
        return FileResponse(f, media_type="image/svg+xml", headers={
            "Cache-Control": "public, max-age=86400", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

    app.mount("/avatars", StaticFiles(directory=STATIC_DIR / "avatars"), name="avatars")
    app.mount("/admin", FreshStaticFiles(directory=STATIC_DIR / "admin", html=True), name="admin")
    return app


def app_from_env() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    return create_app()
