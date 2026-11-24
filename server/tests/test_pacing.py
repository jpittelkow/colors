"""YouTube's "Sign in to confirm you're not a bot" pauses the whole queue instead of failing every video
(2026-11-24: 377 downloads failed in two hours that way)."""
from __future__ import annotations

import time

from app.downloads import jobs, pacing

BOT = "ERROR: [youtube] abc: Sign in to confirm you’re not a bot. This helps protect our community."


def add(env, *vids):
    urls = [f"https://example.test/watch?v={v}" for v in vids]
    return env.client.post("/api/admin/add", json={"urls": urls, "approve": True}).json()["added"]


def jobs_of(env):
    with env.db.conn() as c:
        return [tuple(r) for r in c.execute("SELECT state, attempts FROM jobs ORDER BY id")]


def test_a_bot_check_pauses_the_queue_without_using_up_tries(env):
    real = env.fake.download
    calls = []

    def download(url, on_progress=lambda p: None):
        calls.append(url)
        raise RuntimeError(BOT)

    env.fake.download = download
    add(env, "a", "b", "c")
    env.run_jobs()
    assert len(calls) == 1  # the first answer stops the queue: the others are not even tried
    assert jobs_of(env) == [("queued", 0), ("queued", 0), ("queued", 0)]
    until = pacing.blocked_until(env.db)
    assert 3500 < until - time.time() <= 3600
    assert jobs.retry_failed(env.db, max_attempts=jobs.AUTO_ATTEMPTS) == 0  # the 6-hourly retry waits too
    assert env.client.get("/api/admin/activity").json()["youtube_break"]["until"] == until

    pacing.end_break(env.db)  # a parent says go on (or the hour is over)
    env.fake.download = real
    env.run_jobs()
    assert [s for s, _ in jobs_of(env)] == ["done", "done", "done"]
    assert env.db.get_setting(pacing.COUNT) == "0"  # it worked: the streak is over


def test_blocks_in_a_row_take_longer_breaks(env):
    now = 1_000_000.0
    first = pacing.note_block(env.db, now) - now
    pacing.end_break(env.db)
    second = pacing.note_block(env.db, now + 7200) - (now + 7200)
    pacing.end_break(env.db)
    third = pacing.note_block(env.db, now + 4 * 86400) - (now + 4 * 86400)  # days later: a fresh start
    assert (first, second, third) == (3600, 3 * 3600, 3600)


def test_other_errors_still_fail_as_before(env):
    env.fake.fail = True  # "boom"
    add(env, "a")
    env.run_jobs()
    assert jobs_of(env) == [("failed", 1)] and pacing.blocked_until(env.db) == 0
