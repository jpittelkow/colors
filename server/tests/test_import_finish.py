"""What happens when an import finishes, is stopped, or is cut off by a restart (2026-11-23)."""
from __future__ import annotations

import time

import pytest

from app.downloads import importer


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


def _read(env, text: str) -> tuple[int, list[dict]]:
    iid = env.client.post("/api/admin/import", json={"source": "paste", "text": text}).json()["id"]
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "review")
    return iid, env.client.get(f"/api/admin/import/{iid}").json()["rows"]


def _state(env, iid: int) -> str:
    return env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"]


def _notices(env) -> list[dict]:
    return env.client.get("/api/admin/activity").json()["imports"]


def test_finish_says_what_downloads_now_and_the_pill_says_so_until_opened(env):
    kid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    iid, rows = _read(env, "https://www.youtube.com/@trains\nhttps://www.youtube.com/watch?v=v1")
    assert [n["state"] for n in _notices(env)] == ["review"]  # read: ready for the parent
    chan = next(r for r in rows if r["kind"] == "channel")
    vid = next(r for r in rows if r["kind"] == "video")
    choices = [{"row_id": chan["id"], "action": "subscribe", "mode": "new", "profile_ids": [kid]},
               {"row_id": vid["id"], "action": "approve", "profile_ids": [kid]}]
    env.client.post(f"/api/admin/import/{iid}/seen")
    assert _notices(env) == []
    assert env.client.post(f"/api/admin/import/{iid}/apply", json={"choices": choices}).status_code == 200
    wait_for(lambda: _state(env, iid) == "done")
    result = env.client.get(f"/api/admin/import/{iid}").json()["result"]
    assert result["videos"] == 1 and result["channels_new"] == 1 and result["channels_now"] == 0
    assert "stopped_after" not in result
    notice = _notices(env)
    assert notice[0]["id"] == iid and notice[0]["state"] == "done" and notice[0]["added"] == 2
    env.client.post(f"/api/admin/import/{iid}/seen")
    assert _notices(env) == []


def test_a_stopped_import_goes_back_to_review_and_carries_on(env, monkeypatch):
    kid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    iid, rows = _read(env, "https://www.youtube.com/watch?v=v1\nhttps://www.youtube.com/watch?v=v2")
    reg, real_add = env.app.state.registry, importer.jobs.add_video

    def add_then_stop(*a, **kw):  # the parent presses Stop while the first video is being added
        out = real_add(*a, **kw)
        reg.stop_job("import-apply")
        return out

    monkeypatch.setattr(importer.jobs, "add_video", add_then_stop)
    choices = [{"row_id": r["id"], "action": "approve", "profile_ids": [kid]} for r in rows]
    env.client.post(f"/api/admin/import/{iid}/apply", json={"choices": choices})
    wait_for(lambda: "import-apply" not in reg.running)
    d = env.client.get(f"/api/admin/import/{iid}").json()
    assert d["import"]["state"] == "review"  # not "finished"
    assert sorted(r["state"] for r in d["rows"]) == ["done", "read"]  # the second waits for the parent again
    assert d["result"]["stopped_after"] == 1 and d["result"]["of"] == 2 and d["result"]["videos"] == 1
    assert _notices(env)[0]["stopped"] is True

    monkeypatch.setattr(importer.jobs, "add_video", real_add)
    left = [r for r in d["rows"] if r["state"] == "read"]
    env.client.post(f"/api/admin/import/{iid}/apply", json={"choices": [
        {"row_id": left[0]["id"], "action": "approve", "profile_ids": [kid]}]})
    wait_for(lambda: _state(env, iid) == "done")
    result = env.client.get(f"/api/admin/import/{iid}").json()["result"]
    assert result["videos"] == 2 and "stopped_after" not in result  # both runs counted, no "stopped" left over


def test_an_import_cut_off_while_adding_goes_back_to_review_at_startup(env):
    iid = importer.create(env.db, "paste", ["https://www.youtube.com/watch?v=v1"])
    with env.db.conn() as c:
        c.execute("UPDATE imports SET state = 'applying' WHERE id = ?", (iid,))
    assert env.app.state.registry.resume() == []  # nothing to start: the choices were only in the job
    assert _state(env, iid) == "review"
