"""Evening out the volume (ADR 0041): measure each downloaded video once, let the TV turn it up or down.

The server only measures. ffmpeg's ebur128 filter reads the sound track (EBU R128: integrated loudness in LUFS and
the true peak) without touching the file. The play answer then carries the gain that brings this video to the
household's target; the TV applies it, with a gentle compressor and a limiter for loud moments inside a video.
Files are never changed, so switching it off is instant and complete.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..db import Database

log = logging.getLogger(__name__)

TARGET_LUFS = -16.0        # a little under YouTube's own -14, for a living room with small children in it
MOST_UP_DB = 10.0          # a very quiet video is lifted at most this much; the limiter catches its peaks
MOST_DOWN_DB = -15.0
SILENT_LUFS = -50.0        # quieter than this is no sound worth levelling (a silent clip, a broken track)
TIMEOUT_S = 900


def ffmpeg_path(ffmpeg_dir: str | None) -> str:
    if ffmpeg_dir:
        for name in ("ffmpeg", "ffmpeg.exe"):
            p = Path(ffmpeg_dir) / name
            if p.exists():
                return str(p)
    return shutil.which("ffmpeg") or "ffmpeg"


def measure(path: Path, ffmpeg: str = "ffmpeg") -> dict:
    """{"lufs": float, "peak": float} for the file's sound. Raises RuntimeError when ffmpeg can't read it."""
    # ebur128, not loudnorm: the same integrated loudness, ten times faster (loudnorm resamples to 192 kHz first;
    # 22 s against 2 s for a 7-minute video on LoudMouth, 2026-11-24).
    p = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-nostdin", "-i", str(path), "-map", "0:a:0", "-vn", "-sn", "-dn",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, timeout=TIMEOUT_S, encoding="utf-8", errors="replace")
    summary = (p.stderr or "").rsplit("Summary:", 1)
    i = re.search(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", summary[-1]) if len(summary) == 2 else None
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS", summary[-1]) if len(summary) == 2 else None
    if p.returncode or not i:
        tail = (p.stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise RuntimeError(f"ffmpeg could not measure it: {tail[0][:200]}")
    return {"lufs": float(i.group(1)), "peak": float(tp.group(1)) if tp else None}  # "-inf": a silent track


def gain_db(lufs: float | None, target: float = TARGET_LUFS) -> float:
    """How much to turn this video up (+) or down (-). 0 when it was never measured or has no real sound."""
    if lufs is None or lufs != lufs or lufs < SILENT_LUFS:
        return 0.0
    return round(max(MOST_DOWN_DB, min(MOST_UP_DB, target - lufs)), 1)


def is_on(db: Database) -> bool:
    return db.get_setting("level_volume", "1") == "1"


def audio_for_play(db: Database, lufs: float | None) -> dict | None:
    """What the TV needs for this video, or None when evening out is off (the TV then plays it as it is)."""
    if not is_on(db):
        return None
    return {"gain_db": gain_db(lufs), "compress": True}


def todo(db: Database) -> list:
    with db.conn() as c:
        return c.execute(
            "SELECT id, title, file_path FROM items WHERE source = 'local' AND status = 'ready' AND file_path != '' "
            "AND loudness_at IS NULL ORDER BY added_at DESC").fetchall()


def counts(db: Database) -> dict:
    with db.conn() as c:
        r = c.execute(
            "SELECT count(*), sum(loudness_at IS NOT NULL) FROM items WHERE source = 'local' AND status = 'ready' "
            "AND file_path != ''").fetchone()
    return {"videos": r[0] or 0, "measured": r[1] or 0}


def run(db: Database, library_dir: Path, ffmpeg: str, job=None) -> str:
    """Measure every downloaded video that hasn't been yet, newest first. A file ffmpeg can't read is marked done
    with no level (gain 0), so it isn't tried again on every run."""
    rows = todo(db)
    done = failed = 0
    for n, r in enumerate(rows, 1):
        if job is not None:
            if job.stopped():
                break
            job.note(f"Measuring {n} of {len(rows)}")
        lufs = peak = None
        try:
            m = measure(library_dir / r["file_path"], ffmpeg)
            lufs, peak = m["lufs"], m["peak"]
            if lufs != lufs or lufs in (float("inf"), float("-inf")):
                lufs = None
            if peak is not None and peak in (float("inf"), float("-inf")):
                peak = None
            done += 1
        except Exception as exc:  # a missing or broken file must not stop the rest
            log.warning("loudness: item %s: %s", r["id"], exc)
            failed += 1
        with db.conn() as c:
            c.execute("UPDATE items SET loudness_lufs = ?, loudness_peak = ?, loudness_at = ? WHERE id = ?",
                      (lufs, peak, time.time(), r["id"]))
    if not rows:
        return "Every video is measured"
    return f"Measured {done} videos" + (f", {failed} could not be read" if failed else "")
