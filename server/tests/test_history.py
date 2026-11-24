"""A boy's watch history on his page, and clearing it (ADR 0021; built 2026-11-23)."""
from __future__ import annotations

from tests.test_limits import V, _setup


def _play(tv, pid, item, finish=False, duration=100):
    assert tv.post(f"{V}/play", json={"profile_id": pid, "item_id": item}).status_code == 200
    if finish:
        tv.post(f"{V}/heartbeat", json={"profile_id": pid, "item_id": item, "position_s": duration, "state": "ended"})


def test_history_lists_plays_newest_first_with_tv_and_finished(env):
    pid, tv, ids = _setup(env, durations=(100, 100, 100))
    _play(tv, pid, ids[0], finish=True)
    _play(tv, pid, ids[1])
    r = env.client.get("/api/admin/history", params={"profile_id": pid}).json()
    assert r["total"] == 2 and r["more"] is False
    assert [p["item_id"] for p in r["plays"]] == [ids[1], ids[0]]
    assert [p["finished"] for p in r["plays"]] == [False, True]
    assert r["plays"][0]["tv"] == "Office TV" and r["plays"][0]["title"]


def test_history_pages_with_before(env):
    pid, tv, ids = _setup(env, durations=(100, 100, 100))
    for item in ids:
        _play(tv, pid, item)
    first = env.client.get("/api/admin/history", params={"profile_id": pid, "limit": 2}).json()
    assert len(first["plays"]) == 2 and first["more"] is True
    rest = env.client.get("/api/admin/history", params={"profile_id": pid, "limit": 2, "before": first["plays"][-1]["id"]}).json()
    assert [p["item_id"] for p in rest["plays"]] == [ids[0]] and rest["more"] is False


def test_clearing_history_keeps_todays_minutes_and_the_other_boy(env):
    other = env.client.post("/api/admin/profiles", json={"name": "Alex"}).json()["id"]  # before the videos: they are for both
    pid, tv, ids = _setup(env, durations=(100, 100))
    _play(tv, pid, ids[0], finish=True)
    _play(tv, other, ids[1])
    with env.db.conn() as c:
        minutes_before = c.execute("SELECT sum(seconds) FROM watch_time WHERE profile_id = ?", (pid,)).fetchone()[0]
    assert env.client.delete("/api/admin/history", params={"profile_id": pid}).json()["cleared"] == 2
    assert env.client.get("/api/admin/history", params={"profile_id": pid}).json()["total"] == 0
    assert env.client.get("/api/admin/history", params={"profile_id": other}).json()["total"] == 1
    with env.db.conn() as c:
        assert c.execute("SELECT count(*) FROM watch_state WHERE profile_id = ?", (pid,)).fetchone()[0] == 0
        assert c.execute("SELECT sum(seconds) FROM watch_time WHERE profile_id = ?", (pid,)).fetchone()[0] == minutes_before
    assert env.client.delete("/api/admin/history", params={"profile_id": 9999}).status_code == 404


def test_history_needs_the_parents_sign_in(env):
    from fastapi.testclient import TestClient
    assert TestClient(env.app).get("/api/admin/history", params={"profile_id": 1}).status_code == 401


def test_week_repeats_carry_the_history_details(env):
    pid, tv, ids = _setup(env, durations=(100, 100))
    _play(tv, pid, ids[0], finish=True)
    _play(tv, pid, ids[0])
    _play(tv, pid, ids[1])
    again = env.client.get("/api/admin/reports", params={"profile_id": pid}).json()["again"]
    assert len(again) == 1
    r = again[0]
    assert r["id"] == ids[0] and r["plays"] == 2 and r["finished"] is True
    assert r["tv"] == "Office TV" and r["channel"] and r["last_ts"] and "has_thumb" in r and r["duration_s"] == 100
