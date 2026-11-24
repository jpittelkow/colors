"""Live download progress, kept in memory (ADR 0032, revised 2026-11-23).

The worker writes here a few times a second; the Downloads page and the activity pill read it. Nothing here is
stored: after a restart a running job simply goes back in the queue.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_live: dict[int, dict] = {}
_cancel: set[int] = set()


class Cancelled(Exception):
    """Raised inside the download when a parent pressed Stop."""


def start(job_id: int, phase: str = "Getting ready") -> None:
    with _lock:
        _live[job_id] = {"phase": phase, "percent": None, "downloaded": 0, "total": 0, "speed": 0.0, "eta": None,
                         "started_at": time.time(), "updated_at": time.time()}


def update(job_id: int, **fields) -> None:
    with _lock:
        row = _live.setdefault(job_id, {"started_at": time.time()})
        row.update(fields)
        row["updated_at"] = time.time()


def set_phase(job_id: int, phase: str) -> None:
    """A stage with no percentage: merging, finishing, checking."""
    update(job_id, phase=phase, percent=None, speed=0.0, eta=None)


def get(job_id: int) -> dict | None:
    with _lock:
        row = _live.get(job_id)
        return dict(row, stopping=job_id in _cancel) if row else None


def clear(job_id: int) -> None:
    with _lock:
        _live.pop(job_id, None)
        _cancel.discard(job_id)


def request_cancel(job_id: int) -> None:
    with _lock:
        _cancel.add(job_id)


def cancel_requested(job_id: int) -> bool:
    with _lock:
        return job_id in _cancel
