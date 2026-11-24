"""Named background jobs with a record of every run (ADR 0032).

One thread decides what is due; each run gets its own thread, and a job never runs twice at once. A run gets a
`Run` it can use to say what it is doing (`note`) and to see whether a parent pressed Stop (`stopped`).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .db import Database

log = logging.getLogger("kidtube.jobs")

KEEP_RUNS = 200
START_DELAY_S = 20
MIN_EVERY_S = 300


@dataclass
class Job:
    name: str
    label: str
    about: str
    fn: Callable[["Run"], str]
    every_s: float | None = None          # None: only when a parent presses Run now (or code asks)
    stoppable: bool = False
    enabled: Callable[[Database], bool] = lambda db: True
    disabled_note: str = ""
    listed: bool = True                   # False: started by code only (imports), not shown with Run now
    resume: Callable[[Database], object] | None = None  # at startup: the arg of a run a restart cut off, or None


@dataclass
class Run:
    job: Job
    db: Database
    state: object                          # app.state: downloader, cfg, pics...
    by_hand: bool = False
    arg: object = None
    run_id: int = 0
    note_text: str = ""
    started: float = field(default_factory=time.time)
    _stop: threading.Event = field(default_factory=threading.Event)

    def note(self, text: str) -> None:
        self.note_text = text

    def stopped(self) -> bool:
        return self._stop.is_set()


class Registry(threading.Thread):
    def __init__(self, db: Database, state, jobs: list[Job], tick_s: float = 15):
        super().__init__(name="kidtube-jobs", daemon=True)
        self.db, self.state, self.tick_s = db, state, tick_s
        self.jobs = {j.name: j for j in jobs}
        self.running: dict[str, Run] = {}
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self._wake = threading.Event()
        self._born = time.time()

    # ---- what the page sees ----------------------------------------------------------------------------------------

    def last_runs(self) -> dict[str, dict]:
        with self.db.conn() as c:
            rows = c.execute(
                "SELECT r.* FROM job_runs r JOIN (SELECT job, max(id) AS id FROM job_runs "
                "WHERE state <> 'running' GROUP BY job) m ON m.id = r.id"
            ).fetchall()
        return {r["job"]: dict(r) for r in rows}

    def every(self, job: Job) -> float | None:
        """How often the job runs: the parent's own setting if there is one, else the built-in one."""
        if job.every_s is None:
            return None
        try:
            own = float(self.db.get_setting(f"job_every:{job.name}") or 0)
        except ValueError:
            own = 0
        return own if own >= MIN_EVERY_S else job.every_s

    def next_run(self, job: Job, last: dict | None) -> float | None:
        every = self.every(job)
        if every is None:
            return None
        if not last:
            return self._born + START_DELAY_S
        return last["started_at"] + every

    def describe(self) -> list[dict]:
        last = self.last_runs()
        paused = self.db.get_setting("checks_paused") == "1"
        out = []
        for j in self.jobs.values():
            if not j.listed:
                continue
            run = self.running.get(j.name)
            on = j.enabled(self.db)
            out.append({
                "name": j.name, "label": j.label, "about": j.about, "stoppable": j.stoppable,
                "every_s": self.every(j), "default_every_s": j.every_s, "enabled": on, "disabled_note": "" if on else j.disabled_note,
                "running": bool(run), "note": run.note_text if run else "", "started_at": run.started if run else None,
                "last": last.get(j.name), "next_at": None if (paused or not on) else self.next_run(j, last.get(j.name)),
            })
        return out

    def history(self, name: str, limit: int = 20) -> list[dict]:
        with self.db.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM job_runs WHERE job = ? ORDER BY id DESC LIMIT ?", (name, limit))]

    # ---- starting and stopping ---------------------------------------------------------------------------------------

    def start_job(self, name: str, *, by_hand: bool = True, arg=None, wait: bool = False) -> bool:
        """Start a run now. False if it is already running or does not exist."""
        job = self.jobs.get(name)
        if not job:
            return False
        with self._lock:
            if name in self.running:
                return False
            run = Run(job, self.db, self.state, by_hand=by_hand, arg=arg)
            self.running[name] = run
        with self.db.conn() as c:
            run.run_id = c.execute(
                "INSERT INTO job_runs (job, started_at, by_hand) VALUES (?, ?, ?)", (name, run.started, int(by_hand))
            ).lastrowid
        if wait:
            self._execute(run)
        else:
            threading.Thread(target=self._execute, args=(run,), name=f"kidtube-job-{name}", daemon=True).start()
        return True

    def stop_job(self, name: str) -> bool:
        run = self.running.get(name)
        if not run or not run.job.stoppable:
            return False
        run._stop.set()
        return True

    def _execute(self, run: Run) -> None:
        state, result, error = "done", "", ""
        try:
            result = run.job.fn(run) or ""
            if run.stopped():
                state = "stopped"
        except Exception as exc:  # recorded for the Jobs page; the thread carries on
            log.exception("job %s failed", run.job.name)
            state, error = "failed", str(exc)[:1000]
        finally:
            with self.db.conn() as c:
                c.execute(
                    "UPDATE job_runs SET finished_at = ?, state = ?, result = ?, error = ? WHERE id = ?",
                    (time.time(), state, result[:500], error, run.run_id),
                )
                c.execute(
                    "DELETE FROM job_runs WHERE job = ? AND id NOT IN "
                    "(SELECT id FROM job_runs WHERE job = ? ORDER BY id DESC LIMIT ?)",
                    (run.job.name, run.job.name, KEEP_RUNS),
                )
            with self._lock:
                self.running.pop(run.job.name, None)

    # ---- the loop ----------------------------------------------------------------------------------------------------

    def due(self, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        if self.db.get_setting("checks_paused") == "1":
            return []
        last = self.last_runs()
        out = []
        for j in self.jobs.values():
            nxt = self.next_run(j, last.get(j.name))
            if nxt is not None and nxt <= now and j.name not in self.running and j.enabled(self.db):
                out.append(j.name)
        return out

    def resume(self) -> list[str]:
        """Start again what a restart cut off, for the jobs that know how to carry on. Returns their names."""
        started = []
        for j in self.jobs.values():
            if not j.resume:
                continue
            try:
                arg = j.resume(self.db)
            except Exception:
                log.exception("job %s could not look for unfinished work", j.name)
                continue
            if arg is not None and self.start_job(j.name, by_hand=True, arg=arg):
                started.append(j.name)
        return started

    def run(self) -> None:
        with self.db.conn() as c:  # runs cut off by a restart
            c.execute("UPDATE job_runs SET state = 'stopped', finished_at = ?, error = 'Server restarted' "
                      "WHERE state = 'running'", (time.time(),))
        self.resume()
        while not self._halt.is_set():
            try:
                for name in self.due():
                    self.start_job(name, by_hand=False)
            except Exception:
                log.exception("job loop error")
            self._halt.wait(self.tick_s)

    def stop(self) -> None:
        for run in list(self.running.values()):
            run._stop.set()
        self._halt.set()
