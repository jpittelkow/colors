from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.downloads import jobs, ytdlp_update
from app.downloads.ytdlp import Downloaded, Listing, VideoInfo
from app.main import create_app


class FakeDownloader:
    """Stands in for yt-dlp: no network in tests (ADR 0029)."""

    def __init__(self, library_dir: Path):
        self.library_dir = library_dir
        self.fail = False
        self.channel_videos = [("c1", 300), ("c2", 40), ("c3", 600)]
        self.segs = []
        self.description = ""
        self.channel_of: dict[str, tuple[str, str]] = {}  # video id -> (channel id, title); default chan1 "Trains"

    def segments(self, video_id: str, categories: list[str]):
        return list(self.segs)

    def _info(self, vid: str) -> VideoInfo:
        cid, ctitle = self.channel_of.get(vid, ("chan1", "Trains"))
        return VideoInfo(
            external_id=vid, url=f"https://example.test/watch?v={vid}", title=f"Video {vid}", duration_s=100,
            upload_date="2026-01-02", channel_id=cid, channel_title=ctitle,
        )

    def channel_avatar(self, channel_id: str):
        return "Trains", "https://yt3.ggpht.com/a.jpg"

    def fetch_image(self, url: str, max_bytes: int) -> bytes:
        return b"fakejpg"

    @staticmethod
    def versions() -> dict:
        return {"have": "2026.01.01", "newest": "2026.02.02"}

    def search(self, query: str, count: int = 15):
        return [self._info("s1"), self._info("s2")][:count]

    def look(self, url: str, limit: int = 200) -> Listing:
        if url.endswith("/videos"):
            vids = []
            for vid, dur in self.channel_videos:
                v = self._info(vid)
                v.duration_s = dur
                v.title = f"Channel video {vid}"
                vids.append(v)
            return Listing("list", "Trains", vids[:limit], channel_id="chan1", avatar_url="https://example.test/a.jpg",
                           is_channel=True)
        if "list" in url:
            return Listing("list", "A playlist", [self._info("p1"), self._info("p2")])
        return Listing("video", "", [self._info(url.rsplit("=", 1)[-1])])

    def download(self, url: str, on_progress=lambda p: None) -> Downloaded:
        if self.fail:
            raise RuntimeError("boom")
        vid = url.rsplit("=", 1)[-1]
        cid, ctitle = self.channel_of.get(vid, ("chan1", "Trains"))
        folder = self.library_dir / f"{ctitle} [{cid}]"
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / f"2026-01-02 - Video {vid} [{vid}].mp4"
        f.write_bytes(b"0123456789" * 100)
        t = f.with_suffix(".jpg")
        t.write_bytes(b"jpg")
        on_progress(0.5)
        info = self._info(vid)
        info.description = self.description
        return Downloaded(info, f, t)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "RETRY_DELAYS", ())  # a failure is final at once, unless a test sets delays
    # Never a real pip install from a test: the daily yt-dlp job updates by itself when the fake says one is out.
    monkeypatch.setattr(ytdlp_update, "update", lambda data_dir: {"updated": True, "from": "2026.01.01", "version": "2026.02.02"})
    cfg = Config(data_dir=tmp_path / "data", library_dir=tmp_path / "library", run_worker=False)
    fake = FakeDownloader(cfg.library_dir)
    app = create_app(cfg, downloader=fake)
    client = TestClient(app)
    assert client.post("/api/admin/auth/setup", json={"password": "secret-pw"}).status_code == 200

    class Env:
        pass

    e = Env()
    e.app, e.client, e.cfg, e.fake, e.db = app, client, cfg, fake, app.state.db
    e.run_jobs = lambda: [None for _ in iter(lambda: jobs.run_one(e.db, fake, cfg.library_dir), False)]

    def pair(name="Office TV") -> dict:
        tv = TestClient(app)  # a separate client: a TV has no admin cookie
        started = tv.post("/api/tv/v1/pair/start").json()
        assert client.post("/api/admin/devices/pair", json={"code": started["code"], "name": name}).status_code == 200
        tv.headers["Authorization"] = f"Bearer {started['token']}"
        return {"client": tv, "token": started["token"]}

    e.pair = pair
    return e
