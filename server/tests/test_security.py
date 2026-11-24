"""Fixes from the security review of the overnight build."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_limits import V, _setup


def test_stream_is_cut_after_a_parent_stops_it(env):
    pid, tv, ids = _setup(env)
    play = tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]}).json()
    player = TestClient(env.app)
    assert player.get(play["stream_url"], headers={"Range": "bytes=0-9"}).status_code == 206
    env.client.post(f"/api/admin/kids/{pid}/lock", json={})
    assert player.get(play["stream_url"], headers={"Range": "bytes=0-9"}).status_code == 403


def test_heartbeat_for_another_item_gets_no_exemption(env):
    pid, tv, ids = _setup(env)
    tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]})
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 1})
    # ids[2] (25 min) does not fit and was never started with /play
    r = tv.post(f"{V}/heartbeat", json={"profile_id": pid, "item_id": ids[2], "position_s": 1}).json()
    assert r["command"] == "stop"


def test_password_change_signs_out_other_sessions(env):
    other = TestClient(env.app)
    assert other.post("/api/admin/auth/login", json={"password": "secret-pw"}).status_code == 200
    assert other.get("/api/admin/items").status_code == 200
    r = env.client.post("/api/admin/auth/change", json={"current": "secret-pw", "new": "another-pw"})
    assert r.status_code == 200
    assert other.get("/api/admin/items").status_code == 401
    assert env.client.get("/api/admin/items").status_code == 200  # the changer keeps a fresh cookie


def test_plex_address_change_needs_the_token_again(env):
    env.db.set_setting("plex_url", "http://plex.test:32400")
    env.db.set_setting("plex_token", "tok")
    assert env.client.put("/api/admin/plex", json={"url": "http://elsewhere.test:80"}).status_code == 422
    assert env.client.put("/api/admin/plex", json={"url": "file:///etc/passwd", "token": "x"}).status_code == 422
    assert env.client.put("/api/admin/plex", json={"url": "http://elsewhere.test:80", "token": "   "}).status_code == 422


def test_stream_needs_the_started_item_and_heartbeats_once_over(env):
    import time as _t

    pid, tv, ids = _setup(env)
    a = tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[0]}).json()
    b = tv.post(f"{V}/play", json={"profile_id": pid, "item_id": ids[1]}).json()  # now ids[1] is the started one
    env.client.post(f"/api/admin/kids/{pid}/limit", json={"minutes": 5})
    with env.db.conn() as c:
        c.execute("UPDATE overrides SET ends_at = ? WHERE kind = 'oneoff'", (_t.time() - 30,))
    player = TestClient(env.app)
    assert player.get(a["stream_url"], headers={"Range": "bytes=0-9"}).status_code == 403  # not the started one
    assert player.get(b["stream_url"], headers={"Range": "bytes=0-9"}).status_code == 206
    with env.db.conn() as c:  # the TV stopped sending heartbeats
        c.execute("UPDATE devices SET last_heartbeat = ?", (_t.time() - 300,))
    assert player.get(b["stream_url"], headers={"Range": "bytes=0-9"}).status_code == 403
