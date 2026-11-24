"""Unsubscribing and "Not for them" stop downloads; the retry job leaves them alone (2026-11-23).

The owner: "If I unsubscribe to a channel, we should not download more videos."
"""
from __future__ import annotations

from app.downloads import jobs as jobs_mod
from app.downloads import subscriptions


def _job_states(env) -> dict[str, tuple[str, int]]:
    with env.db.conn() as c:
        return {r["external_id"]: (r["state"], r["stopped"]) for r in c.execute(
            "SELECT i.external_id, j.state, j.stopped FROM jobs j JOIN items i ON i.id = j.item_id")}


def _subscribe_last(env, n=3) -> dict:
    env.client.post("/api/admin/profiles", json={"name": "Sam"})
    rules = {"mode": "last", "last_n": n, "daily_cap": 10}
    return env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains", "rules": rules}).json()


def test_unsubscribe_stops_what_the_subscription_queued(env):
    r = _subscribe_last(env)
    queued = [k for k, (s, _) in _job_states(env).items() if s == "queued"]
    assert queued  # the subscription queued its latest videos
    # A video from the same channel that a parent added by hand keeps downloading.
    env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=byhand"], "approve": True})
    out = env.client.delete(f"/api/admin/subscriptions/{r['subscription_id']}").json()
    assert out["stopped"] == len(queued)
    states = _job_states(env)
    assert all(states[k] == ("failed", 1) for k in queued)  # shown as Stopped in Downloads
    assert states["byhand"] == ("queued", 0)
    env.run_jobs()  # the worker downloads only the hand-added one
    assert _job_states(env)["byhand"][0] == "done"
    assert jobs_mod.retry_failed(env.db) == 0  # and the retry job does not bring the others back


def test_a_check_running_while_unsubscribing_adds_nothing_more(env, monkeypatch):
    r = _subscribe_last(env, n=1)
    sid = r["subscription_id"]
    env.fake.channel_videos.insert(0, ("late1", 400))
    env.fake.channel_videos.insert(0, ("late2", 400))
    real_add = jobs_mod.add_video

    def add_then_unsubscribe(*a, **kw):  # the parent unsubscribes while the check is adding
        out = real_add(*a, **kw)
        subscriptions.unsubscribe(env.db, sid)
        return out

    monkeypatch.setattr(subscriptions.jobs, "add_video", add_then_unsubscribe)
    with env.db.conn() as c:
        c.execute("UPDATE subscriptions SET last_n = 5 WHERE id = ?", (sid,))
    subscriptions.check(env.db, env.fake, sid)
    added = [k for k in _job_states(env) if k.startswith("late")]
    assert len(added) == 1  # the one being added when the parent pressed it; nothing after


def test_not_for_them_stops_the_download_and_the_retry_job_leaves_it(env):
    env.client.post("/api/admin/profiles", json={"name": "Sam"})
    ids = [env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v=n{i}"], "approve": False})
           .json()["added"][0] for i in range(3)]
    # one of them had failed earlier and is due a retry
    with env.db.conn() as c:
        c.execute("UPDATE jobs SET state = 'failed', stopped = 0 WHERE item_id = ?", (ids[2],))
    out = env.client.post("/api/admin/items/decide", json={"ids": ids, "approval": "hidden"}).json()
    assert out == {"decided": 3, "stopped": 3}
    assert set(_job_states(env).values()) == {("failed", 1)}
    assert jobs_mod.retry_failed(env.db) == 0
    env.run_jobs()
    assert set(_job_states(env).values()) == {("failed", 1)}  # nothing downloaded


def test_approving_does_not_stop_anything(env):
    env.client.post("/api/admin/profiles", json={"name": "Sam"})
    iid = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=ok1"], "approve": False}).json()["added"][0]
    assert env.client.post("/api/admin/items/decide", json={"ids": [iid], "approval": "approved"}).json()["stopped"] == 0
    assert _job_states(env)["ok1"] == ("queued", 0)
