"""The list of named background jobs (ADR 0032). Each one is a thin wrapper around the module that does the work."""
from __future__ import annotations

import json
import time

from .ai import openrouter, picks, suggest
from .downloads import importer, subscriptions
from .jobs_registry import Job, Run
from .sources import plex

HOUR = 3600


def _check_channels(run: Run) -> str:
    db, downloader = run.db, run.state.downloader
    with db.conn() as c:
        if run.by_hand:
            ids = [r[0] for r in c.execute("SELECT id FROM subscriptions WHERE active = 1")]
        else:
            ids = subscriptions.due(db)
        names = dict(c.execute("SELECT s.id, c.title FROM subscriptions s JOIN containers c ON c.id = s.container_id"))
    found, failed = 0, 0
    for n, sid in enumerate(ids, 1):
        if run.stopped():
            break
        run.note(f"Checking {names.get(sid, 'a channel')} ({n} of {len(ids)})")
        r = subscriptions.check(db, downloader, sid)
        found += r.get("queued", 0)
        failed += 1 if r.get("error") else 0
    if not ids:
        return "No channel was due"
    return f"Checked {len(ids)} channels, {found} new videos" + (f", {failed} checks failed" if failed else "")


def _retention(run: Run) -> str:
    n = subscriptions.apply_retention(run.db, run.state.cfg.library_dir)
    return f"Deleted {n} videos" if n else "Nothing to delete"


def _plex(run: Run) -> str:
    return f"Refreshed {plex.resync(run.db)} shows"


def _plex_on(db) -> bool:
    url, token = plex.config(db)
    return bool(url and token)


def _pictures(run: Run) -> str:
    from .downloads import jobs

    moved = jobs.repair_unknown(run.db, run.state.downloader)
    out = run.state.pics.refresh(run)
    return f"{out}; {moved} videos moved to their real channel" if moved else out


def _ytdlp(run: Run) -> str:
    v = run.state.downloader.versions()
    run.db.set_setting("ytdlp_versions", json.dumps({**v, "checked_at": time.time()}))
    if v["have"] == v["newest"]:
        return f"yt-dlp {v['have']} is the newest"
    return f"yt-dlp {v['have']} installed, {v['newest']} available: rebuild the image to update"


def _retry_failed(run: Run) -> str:
    from .downloads import jobs

    n = jobs.retry_failed(run.db, max_attempts=None if run.by_hand else jobs.AUTO_ATTEMPTS)
    return f"{n} failed downloads back in the queue" if n else "Nothing to retry"


def _suggest(run: Run) -> str:
    return suggest.run(run.db, run.state.downloader, run)


def _picks(run: Run) -> str:
    return picks.run(run.db, run)


def _ai_ready(db) -> bool:
    return openrouter.is_on(db) and not openrouter.over_cap(db)


AI_OFF = "Turn on AI in Settings › AI. It also pauses when the monthly cap is reached."


def all_jobs() -> list[Job]:
    return [
        Job("channels", "Check channels", "Looks for new videos on subscribed channels that are due.",
            _check_channels, every_s=10 * 60, stoppable=True),
        Job("retry-failed", "Retry failed downloads",
            "Tries failed downloads again, after the two quick tries each download gets by itself. Gives up after 6 tries.",
            _retry_failed, every_s=6 * HOUR),
        Job("cleanup", "Clean up", "Deletes videos that channel keeping rules no longer keep.", _retention,
            every_s=6 * HOUR),
        Job("plex", "Refresh Plex", "Picks up new episodes of allowed Plex shows.", _plex, every_s=6 * HOUR,
            enabled=_plex_on, disabled_note="Plex is not connected."),
        Job("pictures", "Channel pictures", "Fetches missing channel pictures and refreshes ones older than 30 days.",
            _pictures, every_s=24 * HOUR, stoppable=True),
        Job("ytdlp", "yt-dlp version", "Checks for a newer yt-dlp. Updating means rebuilding the server image.",
            _ytdlp, every_s=24 * HOUR),
        Job("ai-suggest", "AI suggestions", "Asks the AI for channels to consider; they land in Add › Ideas.",
            _suggest, every_s=7 * 24 * HOUR, stoppable=True, enabled=_ai_ready, disabled_note=AI_OFF),
        Job("ai-picks", "Picked for you", "Rebuilds each boy's “Picked for you” row from his approved videos.",
            _picks, every_s=6 * HOUR, stoppable=True, enabled=_ai_ready, disabled_note=AI_OFF),
        Job("import-read", "Reading an import", "", importer.read, stoppable=True, listed=False,
            resume=importer.unfinished),
        Job("import-apply", "Adding an import", "", importer.apply, stoppable=True, listed=False,
            resume=importer.reopen_cut_off),
    ]
