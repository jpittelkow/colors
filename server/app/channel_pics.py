"""Channel pictures, looked up in the background and kept on our server (ADR 0030).

Search answers at once; the page shows letters, then swaps in pictures as they arrive. At most 8 channels are
looked up per search and 2 at a time, so a search never turns into a burst of requests to YouTube.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .db import Database

log = logging.getLogger("kidtube.pics")

CHANNEL_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
REFRESH_S = 30 * 86400
RETRY_FAILED_S = 86400
PER_SEARCH = 8
MAX_BYTES = 2_000_000


def valid(channel_id: str) -> bool:
    return bool(CHANNEL_ID.match(channel_id or ""))


class ChannelPics:
    def __init__(self, db: Database, downloader, data_dir: Path):
        self.db, self.downloader = db, downloader
        self.dir = data_dir / "channel-pics"
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kidtube-pics")
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def file(self, channel_id: str) -> Path | None:
        if not valid(channel_id):
            return None
        f = self.dir / f"{channel_id}.jpg"
        return f if f.exists() else None

    def ready(self, ids: list[str]) -> list[str]:
        return [i for i in ids if self.file(i)]

    def _row(self, channel_id: str):
        with self.db.conn() as c:
            return c.execute("SELECT * FROM channel_cache WHERE channel_id = ?", (channel_id,)).fetchone()

    def known_url(self, channel_id: str) -> str:
        """A picture address we already have, from the cache or a channel in the library."""
        row = self._row(channel_id)
        if row and row["avatar_url"]:
            return row["avatar_url"]
        with self.db.conn() as c:
            r = c.execute(
                "SELECT thumb_url FROM containers WHERE source = 'local' AND external_id = ? AND thumb_url <> ''",
                (channel_id,),
            ).fetchone()
        return r["thumb_url"] if r else ""

    def want(self, ids: list[str], limit: int = PER_SEARCH) -> int:
        """Queue lookups for channels without a picture. Returns how many were queued."""
        queued = 0
        now = time.time()
        for cid in dict.fromkeys(i for i in ids if valid(i)):
            if queued >= limit:
                break
            if self.file(cid):
                continue
            row = self._row(cid)
            if row and row["error"] and now - row["fetched_at"] < RETRY_FAILED_S:
                continue
            with self._lock:
                if cid in self._inflight:
                    continue
                self._inflight.add(cid)
            self._pool.submit(self._fetch_quietly, cid)
            queued += 1
        return queued

    def _fetch_quietly(self, cid: str) -> None:
        try:
            self.fetch(cid)
        except Exception as exc:
            log.info("channel picture for %s failed: %s", cid, exc)
        finally:
            with self._lock:
                self._inflight.discard(cid)

    def fetch(self, cid: str, *, url: str = "", fresh: bool = False) -> bool:
        """Look up and save one channel's picture. True when a picture was saved."""
        if not valid(cid):
            return False
        title = ""
        error = ""
        url = url or ("" if fresh else self.known_url(cid))
        try:
            if not url:
                title, url = self.downloader.channel_avatar(cid)
            if not url:
                raise ValueError("The channel has no picture.")
            data = self.downloader.fetch_image(url, MAX_BYTES)
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / f"{cid}.part"
            tmp.write_bytes(data)
            tmp.replace(self.dir / f"{cid}.jpg")
        except Exception as exc:
            error = str(exc)[:300] or "failed"
        with self.db.conn() as c:
            c.execute(
                "INSERT INTO channel_cache (channel_id, title, avatar_url, file, fetched_at, error) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (channel_id) DO UPDATE SET "
                "title = CASE WHEN excluded.title <> '' THEN excluded.title ELSE channel_cache.title END, "
                "avatar_url = CASE WHEN excluded.avatar_url <> '' THEN excluded.avatar_url ELSE channel_cache.avatar_url END, "
                "file = excluded.file, fetched_at = excluded.fetched_at, error = excluded.error",
                (cid, title, url or "", "" if error else f"channel-pics/{cid}.jpg", time.time(), error),
            )
        return not error

    def refresh(self, run) -> str:
        """The scheduled job: pictures for library channels that have none, and ones older than 30 days."""
        now = time.time()
        with self.db.conn() as c:
            library = [r[0] for r in c.execute(
                "SELECT external_id FROM containers WHERE source = 'local' AND kind = 'channel'")]
            old = [r[0] for r in c.execute(
                "SELECT channel_id FROM channel_cache WHERE fetched_at < ? AND error = ''", (now - REFRESH_S,))]
        todo = [i for i in library if valid(i) and not self.file(i)] + old
        todo = list(dict.fromkeys(todo))
        old = set(old)
        got = 0
        for n, cid in enumerate(todo, 1):
            if run.stopped():
                break
            run.note(f"Picture {n} of {len(todo)}")
            if self.fetch(cid, fresh=cid in old):
                got += 1
            time.sleep(1)
        return f"{got} of {len(todo)} pictures updated" if todo else "All pictures are current"
