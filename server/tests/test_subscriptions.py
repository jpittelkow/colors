"""Subscriptions, blocked words, skips and retention (ADR 0004, 0005, 0009, 0024)."""
from __future__ import annotations

from app.downloads import jobs as jobs_mod
from app.downloads import subscriptions


def _profiles(env):
    return [env.client.post("/api/admin/profiles", json={"name": n}).json()["id"] for n in ("Sam", "Alex")]


def test_channel_base():
    assert subscriptions.channel_base("https://www.youtube.com/@Digger/videos") == "https://www.youtube.com/@Digger"
    assert subscriptions.channel_base("https://youtube.com/channel/UC123/shorts") == "https://youtube.com/channel/UC123"


def test_new_uploads_only_ignores_what_is_there(env):
    sam, alex = _profiles(env)
    r = env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains", "trusted": True}).json()
    assert env.client.get("/api/admin/jobs").json() == []
    env.fake.channel_videos.insert(0, ("c9", 400))
    out = env.client.post(f"/api/admin/subscriptions/{r['subscription_id']}/check").json()
    assert out["queued"] == 1
    env.run_jobs()
    ch = env.client.get(f"/api/admin/channels/{r['container_id']}").json()
    assert ch["channel"]["thumb_url"] == "https://example.test/a.jpg"
    assert sorted(ch["profile_ids"]) == [sam, alex]
    assert [i["approval"] for i in ch["items"]] == ["approved"]  # trusted channel


def test_all_mode_applies_rules_and_pacing(env):
    _profiles(env)
    rules = {"mode": "all", "daily_cap": 1, "min_s": 120}
    r = env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains", "rules": rules}).json()
    assert len(env.client.get("/api/admin/jobs").json()) == 1  # c2 is a Short; the cap allows one today
    out = env.client.post(f"/api/admin/subscriptions/{r['subscription_id']}/check").json()
    assert out["queued"] == 0  # still capped
    assert env.client.get("/api/admin/items").json()[0]["approval"] == "waiting"  # not trusted: inbox


def test_blocked_word_in_description_holds_even_trusted(env):
    _profiles(env)
    env.client.put("/api/admin/settings", json={"blocked_words": ["unboxing"]})
    env.fake.channel_videos = [("c1", 300)]
    env.client.post(
        "/api/admin/subscribe",
        json={"url": "https://www.youtube.com/@t", "trusted": True, "rules": {"mode": "last", "last_n": 5}},
    )
    item = env.client.get("/api/admin/items").json()[0]
    assert item["approval"] == "approved"
    env.fake.description = "Big unboxing day!"
    env.run_jobs()
    after = env.client.get(f"/api/admin/items/{item['id']}/detail").json()
    assert after["approval"] == "waiting" and after["blocked_reason"] == "Blocked word: unboxing"
    assert jobs_mod.skip_categories(env.db) == ["sponsor", "selfpromo", "interaction"]


def test_segments_stored_and_sent_to_tv(env):
    pid = _profiles(env)[0]
    env.fake.segs = [{"start_s": 5, "end_s": 20, "category": "sponsor"}]
    r = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=s1"], "approve": True})
    item = r.json()["added"][0]
    env.run_jobs()
    tv = env.pair()["client"]
    play = tv.post("/api/tv/v1/play", json={"profile_id": pid, "item_id": item}).json()
    assert play["skip_segments"] == [{"start_s": 5.0, "end_s": 20.0, "category": "sponsor"}]


def test_retention_keeps_last_n(env):
    _profiles(env)
    rules = {"mode": "last", "last_n": 3, "keep_mode": "last", "keep_n": 1, "skip_shorts": False}
    env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@t", "rules": rules, "trusted": True})
    env.run_jobs()
    assert len([i for i in env.client.get("/api/admin/items").json() if i["status"] == "ready"]) == 3
    assert subscriptions.apply_retention(env.db, env.cfg.library_dir) == 2
    assert len(list(env.cfg.library_dir.rglob("*.mp4"))) == 1


def test_approve_clean_skips_blocked(env):
    _profiles(env)
    env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=a"]})
    with env.db.conn() as c:
        c.execute("UPDATE items SET blocked_reason = 'Blocked word: prank' WHERE external_id = 'a'")
    env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=b"]})
    assert env.client.post("/api/admin/items/approve-clean").json()["approved"] == 1


def test_kids_and_reports_endpoints(env):
    pid = _profiles(env)[0]
    kids = env.client.get("/api/admin/kids").json()
    assert kids[0]["profile"]["name"] == "Sam" and kids[0]["playing"] is None
    rep = env.client.get("/api/admin/reports", params={"profile_id": pid}).json()
    assert len(rep["days"]) == 7
    st = env.client.get("/api/admin/settings").json()
    assert "unboxing" in st["blocked_words"]
    assert env.client.get("/api/admin/plex").json()["connected"] is False


def test_a_channels_youtube_list_shows_what_is_not_in_the_library(env):
    """2026-11-24: the channel page's "Not in library" tab: missing videos, and the ones a parent turned down, noted."""
    env.fake.channel_videos = [("a", 60), ("b", 60), ("c", 60), ("d", 60)]
    r = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=a"], "approve": True}).json()
    rejected = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=b"]}).json()["added"][0]
    env.client.patch(f"/api/admin/items/{rejected}", json={"approval": "hidden"})
    waiting = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=c"]}).json()["added"][0]
    env.run_jobs()
    with env.db.conn() as c:
        cid = c.execute("SELECT container_id FROM items WHERE id = ?", (rejected,)).fetchone()[0]
        c.execute("UPDATE containers SET url = 'https://www.youtube.com/channel/UCtrains' WHERE id = ?", (cid,))
    got = env.client.get(f"/api/admin/channels/{cid}/youtube").json()
    assert got["url"] == "https://www.youtube.com/channel/UCtrains" and got["in_library"] == 1  # "a" is approved
    assert [(v["external_id"], v["state"]) for v in got["videos"]] == [("b", "rejected"), ("c", "waiting"), ("d", "missing")]
    assert next(v for v in got["videos"] if v["state"] == "rejected")["item_id"] == rejected
    assert waiting and r["added"]
