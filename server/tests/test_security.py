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


def test_a_trusted_proxy_secret_signs_the_parent_in(tmp_path):
    """Home Assistant's ingress panel signs the parent in and sends <data>/proxy-secret as a header (ADR 0043)."""
    from fastapi.testclient import TestClient

    from app.config import Config
    from app.main import create_app

    data = tmp_path / "data"
    data.mkdir()
    (data / "proxy-secret").write_text("s3cret-from-ha\n", encoding="utf-8")
    app = create_app(Config(data_dir=data, library_dir=tmp_path / "lib", run_worker=False))
    c = TestClient(app)
    assert c.post("/api/admin/auth/setup", json={"password": "secret-pw"}).status_code == 200
    c.cookies.clear()
    assert c.get("/api/admin/profiles").status_code == 401
    assert c.get("/api/admin/profiles", headers={"X-Kidtube-Proxy": "wrong"}).status_code == 401
    assert c.get("/api/admin/profiles", headers={"X-Kidtube-Proxy": "s3cret-from-ha"}).status_code == 200


def test_no_proxy_secret_file_means_no_header_is_trusted(env):
    env.client.cookies.clear()
    assert env.client.get("/api/admin/profiles", headers={"X-Kidtube-Proxy": ""}).status_code == 401
    assert env.client.get("/api/admin/profiles", headers={"X-Kidtube-Proxy": "anything"}).status_code == 401


def test_an_unreadable_proxy_secret_does_not_stop_the_server(tmp_path, monkeypatch):
    """2026-11-26: a root-owned 600 proxy-secret crashed start-up in the container (it runs as nobody)."""
    from pathlib import Path

    from app.config import Config
    from app.main import create_app

    data = tmp_path / "data"
    data.mkdir()
    (data / "proxy-secret").write_text("x", encoding="utf-8")
    real = Path.read_text

    def deny(self, *a, **k):
        if self.name == "proxy-secret":
            raise PermissionError(13, "Permission denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", deny)
    app = create_app(Config(data_dir=data, library_dir=tmp_path / "lib", run_worker=False))
    assert app.state.proxy_secret == ""
