"""Channels nobody watches (ADR 0042): per child, only what he could reach, suggestions only."""
from __future__ import annotations

import time

from tests.test_limits import V

DAY = 86400


def _setup(env):
    """Two boys, two channels with two videos each, both channels for both boys, both added 60 days ago."""
    sam = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    max_ = env.client.post("/api/admin/profiles", json={"name": "Max"}).json()["id"]
    tv = env.pair()["client"]
    ids = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v=u{n}" for n in range(4)],
                                                  "approve": True}).json()["added"]
    env.run_jobs()
    old = time.time() - 60 * DAY
    with env.db.conn() as c:
        a = c.execute("SELECT container_id FROM items WHERE id = ?", (ids[0],)).fetchone()[0]
        b = c.execute("INSERT INTO containers (source, external_id, title, added_at) VALUES ('local', 'chan2', 'Boats', ?)",
                      (old,)).lastrowid
        c.execute("UPDATE items SET container_id = ? WHERE id IN (?, ?)", (b, ids[2], ids[3]))
        c.execute("UPDATE containers SET added_at = ?", (old,))
        c.execute("UPDATE items SET duration_s = 300")
        c.execute("DELETE FROM assignments")
        for pid in (sam, max_):
            for cid in (a, b):
                c.execute("INSERT INTO assignments (profile_id, container_id) VALUES (?, ?)", (pid, cid))
    return sam, max_, tv, ids, a, b


def _report(env):
    return env.client.get("/api/admin/unwatched").json()


def _by_id(rep):
    return {ch["id"]: ch for ch in rep["channels"]}


def test_lists_channels_per_child_longest_first(env):
    sam, max_, tv, ids, a, b = _setup(env)
    assert tv.post(f"{V}/play", json={"profile_id": sam, "item_id": ids[0]}).status_code == 200
    with env.db.conn() as c:  # Max watched Boats 40 days ago
        c.execute("INSERT INTO events (ts, profile_id, item_id, type) VALUES (?, ?, ?, 'started')",
                  (time.time() - 40 * DAY, max_, ids[2]))
    rep = _report(env)
    assert rep["days"] == 30
    chans = _by_id(rep)
    assert list(chans) == [b, a]  # both 60 days (Max never saw Trains, Sam never saw Boats): A to Z on a tie
    trains = {k["profile_id"]: k for k in chans[a]["kids"]}
    assert trains[sam]["stale"] is False and trains[sam]["days"] == 0
    assert trains[max_]["stale"] is True and trains[max_]["never"] is True and trains[max_]["days"] == 60
    boats = {k["profile_id"]: k for k in chans[b]["kids"]}
    assert boats[max_]["days"] == 40 and boats[max_]["never"] is False and chans[b]["days"] == 60
    assert chans[a]["bytes"] > 0 and chans[a]["videos"] == 2


def test_a_channel_everyone_watched_lately_is_not_listed(env):
    sam, max_, tv, ids, a, b = _setup(env)
    for pid in (sam, max_):
        assert tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]}).status_code == 200
    assert a not in _by_id(_report(env))


def test_new_rested_and_kept_channels_are_left_out(env):
    sam, max_, tv, ids, a, b = _setup(env)
    with env.db.conn() as c:
        c.execute("UPDATE containers SET added_at = ? WHERE id = ?", (time.time() - 5 * DAY, a))  # new: not unloved
    assert list(_by_id(_report(env))) == [b]
    env.client.patch(f"/api/admin/channels/{b}", json={"rested_until": "2099-01-01"})
    assert _report(env)["channels"] == []
    env.client.patch(f"/api/admin/channels/{b}", json={"rested_until": ""})
    assert env.client.post(f"/api/admin/unwatched/{b}/keep").json()["days"] == 90
    assert _report(env)["channels"] == []
    env.client.delete(f"/api/admin/unwatched/{b}/keep")
    assert list(_by_id(_report(env))) == [b]


def test_nothing_to_play_goes_in_its_own_list(env):
    sam, max_, tv, ids, a, b = _setup(env)
    with env.db.conn() as c:
        c.execute("UPDATE items SET status = 'failed' WHERE container_id = ?", (b,))
    rep = _report(env)
    assert b not in _by_id(rep)
    empty = {ch["id"]: ch for ch in rep["empty"]}
    assert empty[b]["failed"] == 2 and empty[b]["profile_ids"] == [sam, max_]


def test_reasons_finished_everything_and_too_long_for_his_day(env):
    sam, max_, tv, ids, a, b = _setup(env)
    old = time.time() - 45 * DAY
    with env.db.conn() as c:
        for item in (ids[0], ids[1]):  # Sam finished both Trains videos, 45 days ago
            c.execute("INSERT INTO watch_state (profile_id, item_id, position_s, watched, updated_at) VALUES (?, ?, 0, 1, ?)",
                      (sam, item, old))
        c.execute("UPDATE items SET duration_s = 1800 WHERE container_id = ?", (b,))
    env.client.put(f"/api/admin/limits/{max_}", json={"weekday_min": 20, "weekend_min": 25})
    chans = _by_id(_report(env))
    trains = {k["profile_id"]: k for k in chans[a]["kids"]}
    assert trains[sam]["reason"] == {"kind": "finished", "videos": 2} and trains[sam]["days"] == 45
    boats = {k["profile_id"]: k for k in chans[b]["kids"]}
    assert boats[max_]["reason"] == {"kind": "too_long", "limit_min": 25, "shortest_min": 30}
    assert boats[sam]["reason"] is None


def test_the_threshold_is_a_setting(env):
    sam, max_, tv, ids, a, b = _setup(env)
    assert env.client.put("/api/admin/settings", json={"unwatched_days": 90}).json()["unwatched_days"] == 90
    assert _report(env)["channels"] == []  # 60 days is not past 90


def test_pausing_a_subscription_keeps_it(env):
    r = env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains"}).json()
    sid = r["subscription_id"]
    assert env.client.patch(f"/api/admin/subscriptions/{sid}", json={"active": False}).json()["active"] is False
    with env.db.conn() as c:
        assert c.execute("SELECT active FROM subscriptions WHERE id = ?", (sid,)).fetchone()[0] == 0
    assert env.client.patch("/api/admin/subscriptions/999", json={"active": True}).status_code == 404
