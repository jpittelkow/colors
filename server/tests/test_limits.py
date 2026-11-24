"""Limits on the server (ADR 0011) and time-fit (ADR 0012)."""
from __future__ import annotations

import time

from app.limits import clock

V = "/api/tv/v1"


def _setup(env, durations=(100, 600, 1500)):
    pid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    tv = env.pair()["client"]
    ids = []
    for n, _ in enumerate(durations):
        r = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v=v{n}"], "approve": True})
        ids.append(r.json()["added"][0])
    env.run_jobs()
    with env.db.conn() as c:
        for item, d in zip(ids, durations):
            c.execute("UPDATE items SET duration_s = ? WHERE id = ?", (d, item))
    return pid, tv, ids


def _visible(tv, pid):
    home = tv.get(f"{V}/home", params={"profile_id": pid}).json()
    new = next((r for r in home["rows"] if r["id"] == "new"), {"cards": []})
    return home, sorted(c["id"] for c in new["cards"])


def test_no_limit_shows_everything(env):
    pid, tv, ids = _setup(env)
    home, vis = _visible(tv, pid)
    assert vis == sorted(ids) and home["time"]["limited"] is False


def test_one_off_limit_only_shows_what_fits(env):
    pid, tv, ids = _setup(env)
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 10})
    home, vis = _visible(tv, pid)
    # 10 min left + 2 min grace: the 100 s and 600 s videos fit, the 25 min one does not
    assert vis == sorted(ids[:2])
    assert 590 <= home["time"]["left_s"] <= 600
    why = env.client.get("/api/admin/why", params={"profile_id": pid, "item_id": ids[2]}).json()
    assert [s["step"] for s in why if not s["ok"]] == ["fits"]
    assert tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[2]}).status_code == 403


def test_resume_point_counts_toward_fit(env):
    pid, tv, ids = _setup(env)
    with env.db.conn() as c:
        c.execute(
            "INSERT INTO watch_state (profile_id, item_id, position_s, watched, updated_at) VALUES (?, ?, 1200, 0, ?)",
            (pid, ids[2], time.time()),
        )
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 5})
    _, vis = _visible(tv, pid)
    assert ids[2] in vis  # 300 s left of a 25 min video fits a 5 min window


def test_skipped_segments_shorten_a_video(env):
    pid, tv, ids = _setup(env, durations=(800,))
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 10})
    _, vis = _visible(tv, pid)
    assert vis == []  # 800 s > 600 s + 120 s grace
    env.client.post(f"/api/admin/items/{ids[0]}/segments", json={"start_s": 0, "end_s": 100})
    _, vis = _visible(tv, pid)
    assert vis == ids


def test_daily_allowance_counts_heartbeats(env):
    pid, tv, ids = _setup(env)
    env.client.put(f"/api/admin/limits/{pid}", json={"weekday_min": 30, "weekend_min": 30, "grace_min": 0})
    tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[1]})
    now = time.time()
    with env.db.conn() as c:
        dev = c.execute("SELECT * FROM devices WHERE paired_at IS NOT NULL").fetchone()
        c.execute(
            "UPDATE devices SET last_state = 'playing', last_profile_id = ?, last_heartbeat = ? WHERE id = ?",
            (pid, now - 15, dev["id"]),
        )
        dev = c.execute("SELECT * FROM devices WHERE id = ?", (dev["id"],)).fetchone()
        assert clock.count_heartbeat(c, dev, pid, "playing", now) == 15
        c.execute("UPDATE watch_time SET seconds = 1200 WHERE profile_id = ?", (pid,))
    home, vis = _visible(tv, pid)
    assert 595 <= home["time"]["left_s"] <= 600 and vis == sorted(ids[:2])
    env.client.post(f"/api/admin/kids/{pid}/extra", json={"minutes": 30})
    _, vis = _visible(tv, pid)
    assert vis == sorted(ids)


def test_time_up_finishes_the_video_then_stops(env):
    pid, tv, ids = _setup(env)
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 5})
    tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]})
    with env.db.conn() as c:  # the one-off limit ran out a minute ago
        c.execute("UPDATE overrides SET ends_at = ? WHERE kind = 'oneoff'", (time.time() - 60,))
    hb = {"profile_id": pid, "item_id": ids[0], "position_s": 50}
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] is None  # within the hard cap: keep playing
    assert tv.post(f"{V}/heartbeat", json=dict(hb, position_s=100, state="ended")).json()["command"] == "timeup"
    home, vis = _visible(tv, pid)
    assert vis == [] and home["time"]["open"] is False
    with env.db.conn() as c:  # far past the limit: stop even mid-video
        c.execute("UPDATE overrides SET ends_at = ? WHERE kind = 'oneoff'", (time.time() - 3600,))
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] == "timeup"


def test_last_one_and_end_now(env):
    pid, tv, ids = _setup(env)
    tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]})
    env.client.post(f"/api/admin/kids/{pid}/lastone", json={})
    hb = {"profile_id": pid, "item_id": ids[0], "position_s": 50}
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] is None
    assert tv.post(f"{V}/heartbeat", json=dict(hb, state="ended")).json()["command"] == "timeup"
    assert _visible(tv, pid)[1] == []
    env.client.post(f"/api/admin/kids/{pid}/unlock", json={})
    assert _visible(tv, pid)[1] == sorted(ids)
    env.client.post(f"/api/admin/kids/{pid}/lock", json={})
    r = tv.post(f"{V}/heartbeat", json=hb).json()
    assert r["command"] == "stop" and r["reason"] == "parent"


def test_last_one_allows_only_one_video(env):
    """The owner, 2026-11-23: "last one" must not let him flick through videos. One start, then that's it."""
    pid, tv, ids = _setup(env)
    env.client.post(f"/api/admin/kids/{pid}/lastone", json={})  # not watching: the next video started is the one
    play = lambda i: tv.post(f"{V}/play", json={"profile_id": pid, "item_id": i})
    assert play(ids[1]).status_code == 200
    refused = play(ids[0])
    assert refused.status_code == 403 and refused.json()["detail"]["reason"] == "lastone"
    assert play(ids[1]).status_code == 200  # the same one again is fine (back out and in, resume)
    home = tv.get(f"{V}/home", params={"profile_id": pid}).json()
    assert [(r["id"], [c["id"] for c in r["cards"]]) for r in home["rows"]] == [("lastone", [ids[1]])]
    assert tv.get(f"{V}/upnext", params={"profile_id": pid, "item_id": ids[1]}).json()["cards"] == []
    assert [c["id"] for c in tv.get(f"{V}/shelf/new", params={"profile_id": pid}).json()["cards"]] == [ids[1]]
    # A stream or heartbeat for another video, from before "last one", stops too.
    assert tv.post(f"{V}/heartbeat", json={"profile_id": pid, "item_id": ids[0], "position_s": 5}).json()["command"] == "timeup"
    with env.db.conn() as c:
        assert clock.claim_lastone(c, pid, ids[2]) is False  # already taken: a second claim loses
    hb = {"profile_id": pid, "item_id": ids[1], "position_s": 600, "state": "ended"}
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] == "timeup"


def test_closed_hours(env):
    pid, tv, ids = _setup(env)
    lt = time.localtime()
    start = f"{lt.tm_hour:02d}:00"
    end = f"{(lt.tm_hour + 1) % 24:02d}:00"
    env.client.put(f"/api/admin/limits/{pid}", json={"closed_from": start, "closed_to": end})
    home, vis = _visible(tv, pid)
    assert vis == [] and home["time"]["reason"] == "Closed now"
    assert home["time"]["opens_at"] == end  # the TV's "Good night" screen says when it opens again
    kids = env.client.get("/api/admin/kids").json()
    assert kids[0]["time"]["open"] is False


def test_day_key_rolls_over_at_four():
    t = time.mktime((2026, 11, 23, 3, 30, 0, 0, 0, -1))
    assert clock.day_key(t) == "2026-11-22"
    assert clock.day_key(t + 3600) == "2026-11-23"


def _midday() -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 12, 0, 0, 0, 0, -1))


def test_unlock_just_unlocks_until_tomorrow(env):
    """The owner, 2026-11-23: Unlock should not be for a time period; it should just unlock. It used to lift only
    End now and closed hours, for an hour, so with daily time used up it did nothing."""
    pid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    env.client.put(f"/api/admin/limits/{pid}", json={"weekday_min": 30, "weekend_min": 30, "grace_min": 0})
    now = _midday()  # far from the day rollover, whenever the tests run
    with env.db.conn() as c:
        c.execute("INSERT INTO watch_time (profile_id, day, seconds) VALUES (?, ?, ?)", (pid, clock.day_key(now), 3600))
        assert clock.context(c, pid, now).open is False  # daily time used up
        clock.add_override(c, pid, "unlock", now=now)
        ctx = clock.context(c, pid, now)
        assert ctx.open is True and ctx.unlocked is True and ctx.limited is False
        assert clock.context(c, pid, now + 2 * 3600).open is True  # not just for an hour
        clock.add_override(c, pid, "oneoff", minutes=15, now=now)  # a limit started after unlocking still counts
        assert clock.context(c, pid, now + 16 * 60).open is False
        clock.add_override(c, pid, "unlock", now=now + 16 * 60)  # and unlocking again lifts it
        assert clock.context(c, pid, now + 16 * 60).open is True
        clock.add_override(c, pid, "lock", now=now)  # End now locks again
        assert clock.context(c, pid, now + 17 * 60).open is False


def test_unlock_lifts_closed_hours_for_the_rest_of_the_day(env):
    pid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    now = _midday()  # far from the day rollover, whenever the tests run
    m = clock._minutes_of_day(now)
    start, end = f"{(m - 30) % 1440 // 60:02d}:{(m - 30) % 60:02d}", f"{(m + 90) % 1440 // 60:02d}:{(m + 90) % 60:02d}"
    env.client.put(f"/api/admin/limits/{pid}", json={"closed_from": start, "closed_to": end})
    with env.db.conn() as c:
        assert clock.context(c, pid, now).open is False
        clock.add_override(c, pid, "unlock", now=now)
        assert clock.context(c, pid, now + 80 * 60).open is True  # past the old one-hour unlock
