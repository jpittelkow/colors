"""An import reads links slowly, and YouTube still refuses some for a moment ("This video is not available"). Those
are asked again; the ones that are gone are not; and a parent can read the rest again later (2026-11-23)."""
from __future__ import annotations

import time

from app.downloads import importer



def wait_for(cond, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    raise AssertionError("timed out")


def states(env, iid):
    with env.db.conn() as c:
        return {r["url"].rsplit("=", 1)[-1]: r["state"] for r in c.execute(
            "SELECT url, state FROM import_rows WHERE import_id = ? ORDER BY id", (iid,))}


def test_a_refused_lookup_is_asked_again_and_a_gone_one_is_not(env, monkeypatch):
    monkeypatch.setattr(importer, "PAUSE_S", 0)
    monkeypatch.setattr(importer, "RETRY_WAITS_S", (0, 0))
    real, calls = env.fake.look, []

    def look(url, limit=200):
        calls.append(url)
        if url.endswith("=flaky") and calls.count(url) == 1:
            raise RuntimeError("ERROR: [youtube] flaky: This video is not available")
        if url.endswith("=gone"):
            raise RuntimeError("ERROR: [youtube] gone: Video unavailable. This video has been removed by the uploader")
        return real(url, limit)

    env.fake.look = look
    iid = importer.create(env.db, "paste", [f"https://www.youtube.com/watch?v={v}" for v in ("ok", "flaky", "gone")])
    env.app.state.registry.start_job("import-read", arg=iid, wait=True)
    assert states(env, iid) == {"ok": "read", "flaky": "read", "gone": "failed"}
    assert calls.count("https://www.youtube.com/watch?v=gone") == 1  # gone: asked once


def test_try_again_reads_the_failed_ones_but_not_the_gone(env, monkeypatch):
    monkeypatch.setattr(importer, "PAUSE_S", 0)
    monkeypatch.setattr(importer, "RETRY_WAITS_S", ())
    real = env.fake.look
    down = {"on": True}

    def look(url, limit=200):
        if url.endswith("=gone"):
            raise RuntimeError("ERROR: [youtube] gone: Private video. Sign in if you've been granted access")
        if down["on"] and url.endswith("=late"):
            raise RuntimeError("ERROR: [youtube] late: This video is not available")
        return real(url, limit)

    env.fake.look = look
    iid = importer.create(env.db, "paste", [f"https://www.youtube.com/watch?v={v}" for v in ("late", "gone")])
    env.app.state.registry.start_job("import-read", arg=iid, wait=True)
    rows = env.client.get(f"/api/admin/import/{iid}").json()["rows"]
    assert {r["url"].rsplit("=", 1)[-1]: (r["state"], r["gone"]) for r in rows} == {"late": ("failed", False), "gone": ("failed", True)}

    down["on"] = False
    assert env.client.post(f"/api/admin/import/{iid}/retry").json() == {"retrying": 1}
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "review")
    assert states(env, iid) == {"late": "read", "gone": "failed"}
    assert env.client.post(f"/api/admin/import/{iid}/retry").status_code == 422  # only the gone one is left
