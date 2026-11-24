"""Milestone 1 end to end: add, download, approve, assign, see it on a TV, play, resume."""
from __future__ import annotations

from fastapi.testclient import TestClient

V = "/api/tv/v1"


def _profile(env, name="Sam") -> int:
    return env.client.post("/api/admin/profiles", json={"name": name}).json()["id"]


def _add(env, vid="abc", **kw) -> int:
    r = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v={vid}"], **kw}).json()
    return (r["added"] or r["already_in_library"])[0]


def test_admin_needs_a_password(env):
    stranger = TestClient(env.app)
    assert stranger.get("/api/admin/items").status_code == 401
    assert stranger.post("/api/admin/auth/setup", json={"password": "another-pw"}).status_code == 409
    assert stranger.post("/api/admin/auth/login", json={"password": "secret-pw"}).status_code == 200
    assert stranger.get("/api/admin/items").status_code == 200


def test_tv_must_be_paired(env):
    tv = TestClient(env.app)
    assert tv.get(f"{V}/profiles").status_code == 401
    started = tv.post(f"{V}/pair/start").json()
    tv.headers["Authorization"] = f"Bearer {started['token']}"
    assert tv.get(f"{V}/pair/status").json()["paired"] is False
    assert tv.get(f"{V}/profiles").status_code == 403
    wrong = "000000" if started["code"] != "000000" else "111111"
    assert env.client.post("/api/admin/devices/pair", json={"code": wrong, "name": "x"}).status_code == 404
    assert tv.get(f"{V}/profiles").status_code == 403


def test_nothing_shows_until_downloaded_approved_and_assigned(env):
    sam, alex = _profile(env, "Sam"), _profile(env, "Alex")
    tv = env.pair()["client"]
    item = _add(env, "abc", profile_ids=[sam])  # waiting, assigned to Sam only

    home = lambda p: tv.get(f"{V}/home", params={"profile_id": p}).json()["rows"]
    assert home(sam) == []  # not downloaded
    env.run_jobs()
    assert home(sam) == []  # downloaded, not approved

    why = env.client.get("/api/admin/why", params={"profile_id": sam, "item_id": item}).json()
    assert [s["step"] for s in why if not s["ok"]] == ["approved"]

    env.client.patch(f"/api/admin/items/{item}", json={"approval": "approved"})
    rows = home(sam)
    assert [r["id"] for r in rows][0] == "new" and rows[0]["cards"][0]["id"] == item
    assert home(alex) == []  # not his

    env.client.post("/api/admin/assign", json={"profile_id": alex, "item_id": item})
    assert home(alex) != []
    env.client.patch(f"/api/admin/items/{item}", json={"approval": "hidden"})
    assert home(sam) == [] and home(alex) == []


def test_play_stream_resume_and_stop_when_hidden(env):
    sam = _profile(env)
    tv = env.pair()["client"]
    item = _add(env, "abc", approve=True)  # default: every child profile
    env.run_jobs()

    played = tv.post(f"{V}/play", json={"profile_id": sam, "item_id": item}).json()
    assert played["resume_s"] == 0
    # The stream needs no header (the player just gets a URL) and answers range requests.
    anyone = TestClient(env.app)
    part = anyone.get(played["stream_url"], headers={"Range": "bytes=0-9"})
    assert part.status_code == 206 and part.content == b"0123456789"
    assert anyone.get(played["stream_url"][:-3] + "abc").status_code == 403  # tampered token

    hb = {"profile_id": sam, "item_id": item, "position_s": 40}
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] is None
    rows = tv.get(f"{V}/home", params={"profile_id": sam}).json()["rows"]
    assert rows[0]["id"] == "continue"
    assert tv.get(rows[0]["cards"][0]["thumb"]).content == b"jpg"
    assert tv.post(f"{V}/play", json={"profile_id": sam, "item_id": item}).json()["resume_s"] == 40

    tv.post(f"{V}/heartbeat", json=dict(hb, position_s=95))  # past 90 %: watched
    rows = tv.get(f"{V}/home", params={"profile_id": sam}).json()["rows"]
    assert rows[0]["id"] == "new" and rows[0]["cards"][0]["watched"] is True

    env.client.patch(f"/api/admin/items/{item}", json={"approval": "hidden"})
    assert tv.post(f"{V}/heartbeat", json=hb).json()["command"] == "stop"
    assert tv.post(f"{V}/play", json={"profile_id": sam, "item_id": item}).status_code == 403
    assert anyone.get(played["stream_url"]).status_code == 403


def test_revoked_tv_loses_access(env):
    _profile(env)
    paired = env.pair()
    tv = paired["client"]
    assert tv.get(f"{V}/profiles").status_code == 200
    dev = env.client.get("/api/admin/devices").json()[0]["id"]
    env.client.delete(f"/api/admin/devices/{dev}")
    assert tv.get(f"{V}/profiles").status_code == 401


def test_no_duplicate_downloads_and_failed_job_retry(env):
    _profile(env)
    first = _add(env, "abc")
    assert _add(env, "abc") == first
    assert len(env.client.get("/api/admin/jobs").json()) == 1

    env.fake.fail = True
    env.run_jobs()
    job = env.client.get("/api/admin/jobs").json()[0]
    assert job["state"] == "failed" and "boom" in job["error"]
    env.fake.fail = False
    env.client.post(f"/api/admin/jobs/{job['id']}/retry")
    env.run_jobs()
    assert env.client.get("/api/admin/items").json()[0]["status"] == "ready"


def test_search_look_and_tags(env):
    _profile(env)
    assert len(env.client.get("/api/admin/search", params={"q": "trains"}).json()) == 2
    listing = env.client.post("/api/admin/look", json={"url": "https://example.test/list"}).json()
    assert listing["kind"] == "list" and len(listing["videos"]) == 2
    item = _add(env, "abc")
    env.client.post("/api/admin/tag", json={"target_type": "item", "target_id": item, "tag": "Learning"})
    assert env.client.get("/api/admin/items").json()[0]["tags"] == ["learning"]


def test_library_lists_filter_by_boy_page_and_decide_in_bulk(env):
    """ADR 0037: the Library and Approve screens' data."""
    sam = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    alex = env.client.post("/api/admin/profiles", json={"name": "Alex"}).json()["id"]
    urls = [f"https://example.test/watch?v=v{i}" for i in range(4)]
    ids = env.client.post("/api/admin/add", json={"urls": urls[:3], "approve": False, "profile_ids": [sam]}).json()["added"]
    env.run_jobs()
    env.fake.fail = True
    failed = env.client.post("/api/admin/add", json={"urls": urls[3:], "approve": False, "profile_ids": [sam]}).json()["added"]
    env.run_jobs()
    waiting = env.client.get("/api/admin/items", params={"approval": "waiting", "hide_failed": True}).json()
    assert sorted(i["id"] for i in waiting) == sorted(ids)  # the failed download is not asked about
    assert waiting[0]["container_external_id"] == "chan1" and waiting[0]["container_source"] == "local"
    assert env.client.post("/api/admin/items/decide", json={"ids": ids[:2], "approval": "approved"}).json() == {"decided": 2}
    assert env.client.post("/api/admin/items/decide", json={"ids": ids[2:], "approval": "hidden"}).status_code == 200
    approved = lambda **p: [i["id"] for i in env.client.get("/api/admin/items", params={"approval": "approved", **p}).json()]
    assert sorted(approved(profile_id=sam)) == sorted(ids[:2]) and approved(profile_id=alex) == []
    assert len(approved(limit=1)) == 1 and approved(limit=1, offset=1) != approved(limit=1)
    chan = env.client.get("/api/admin/channels").json()[0]
    assert chan["approved"] == 2 and chan["seen_by"] == [sam] and chan["waiting"] == 0 and len(failed) == 1


def test_menu_lists_channels_recent_recommended_and_new(env):
    sam, alex = _profile(env, "Sam"), _profile(env, "Alex")
    tv = env.pair()["client"]
    a, b = _add(env, "aaa", approve=True), _add(env, "bbb", approve=True)
    env.run_jobs()

    chans = tv.get(f"{V}/channels", params={"profile_id": sam}).json()["channels"]
    assert sum(c["count"] for c in chans) == 2
    assert tv.get(chans[0]["picture"]).status_code == 200  # no channel picture here: the newest video's thumb

    shelf = lambda kind, p=sam: [c["id"] for c in tv.get(f"{V}/shelf/{kind}", params={"profile_id": p}).json()["cards"]]
    assert shelf("recent") == []
    tv.post(f"{V}/play", json={"profile_id": sam, "item_id": a})
    tv.post(f"{V}/heartbeat", json={"profile_id": sam, "item_id": a, "position_s": 40})
    assert shelf("recent") == [a] and shelf("recent", alex) == []  # one child's history only
    assert sorted(shelf("new")) == sorted([a, b])
    assert shelf("picked") == [b]  # AI off: unwatched and not started
    assert tv.get(f"{V}/shelf/everything", params={"profile_id": sam}).status_code == 404

    env.client.patch(f"/api/admin/items/{b}", json={"approval": "hidden"})
    assert shelf("new") == [a] and shelf("picked") == []  # the same filtering as the home rows
