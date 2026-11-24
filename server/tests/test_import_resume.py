"""An import that a restart cut off carries on by itself (ADR 0035)."""
from __future__ import annotations

import time

import pytest

from app.downloads import importer

LINKS = [f"https://www.youtube.com/watch?v=v{n}" for n in (1, 2, 3)]


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    monkeypatch.setattr(importer, "PAUSE_S", 0)


def wait_for(fn, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.05)
    raise AssertionError("timed out")


def look_at(env, iid: int) -> tuple[str, list[tuple[str, str]]]:
    with env.db.conn() as c:
        state = c.execute("SELECT state FROM imports WHERE id = ?", (iid,)).fetchone()["state"]
        rows = c.execute("SELECT state, title FROM import_rows WHERE import_id = ? ORDER BY id", (iid,)).fetchall()
    return state, [(r["state"], r["title"]) for r in rows]


def test_an_import_left_reading_is_picked_up_at_startup(env):
    reg = env.app.state.registry
    assert importer.unfinished(env.db) is None and reg.resume() == []
    iid = importer.create(env.db, "paste", LINKS)
    with env.db.conn() as c:  # as a restart leaves it: one link read, the rest waiting, no job running
        c.execute("UPDATE import_rows SET state = 'read', kind = 'video', external_id = 'v1', title = 'Read before' "
                  "WHERE import_id = ? AND url = ?", (iid, LINKS[0]))
    assert importer.unfinished(env.db) == iid
    assert reg.resume() == ["import-read"]
    wait_for(lambda: look_at(env, iid)[0] == "review")
    # The link read before the restart is not read again; the others are.
    assert look_at(env, iid)[1] == [("read", "Read before"), ("read", "Video v2"), ("read", "Video v3")]
    wait_for(lambda: "import-read" not in reg.running)
    assert importer.unfinished(env.db) is None and reg.resume() == []


def test_a_read_stopped_by_shutdown_stays_unfinished_and_carries_on(env):
    reg, fake = env.app.state.registry, env.fake
    real_look = fake.look

    def look_while_going_down(url, limit=200):
        reg.stop()  # the server is told to stop while the first link is being read
        return real_look(url, limit)

    fake.look = look_while_going_down
    iid = importer.create(env.db, "paste", LINKS)
    reg.start_job("import-read", arg=iid, wait=True)
    # Not moved on to review with links unread: it is still 'reading', for the next start to find.
    assert look_at(env, iid) == ("reading", [("read", "Video v1"), ("waiting", ""), ("waiting", "")])
    with env.db.conn() as c:
        last = c.execute("SELECT state, result FROM job_runs WHERE job = 'import-read' ORDER BY id DESC").fetchone()
    assert last["state"] == "stopped" and "carries on" in last["result"]

    fake.look = real_look
    assert reg.resume() == ["import-read"]
    wait_for(lambda: look_at(env, iid)[0] == "review")
    assert [s for s, _ in look_at(env, iid)[1]] == ["read", "read", "read"]
