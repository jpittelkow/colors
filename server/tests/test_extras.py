"""Channel pictures, named jobs, import, avatars and AI (ADRs 0030, 0032, 0034, 0035, 0036)."""
from __future__ import annotations

import json
import time

import pytest

from app.ai import openrouter, suggest
from app.downloads import importer


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    monkeypatch.setattr(importer, "PAUSE_S", 0)
    monkeypatch.setattr(suggest, "PAUSE_S", 0)


def wait_for(fn, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.05)
    raise AssertionError("timed out")


def kids(env) -> tuple[int, int]:
    a = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    b = env.client.post("/api/admin/profiles", json={"name": "Alex"}).json()["id"]
    return a, b


# ---- channel pictures (ADR 0030) -----------------------------------------------------------------------------------


def test_search_queues_channel_pictures_and_serves_them(env):
    r = env.client.get("/api/admin/search", params={"q": "trains"}).json()
    assert r[0]["channel_id"] == "chan1"
    wait_for(lambda: env.client.get("/api/admin/channel-pictures", params={"ids": "chan1"}).json()["ready"] == ["chan1"])
    pic = env.client.get("/api/admin/channel-pictures/chan1")
    assert pic.status_code == 200 and pic.content == b"fakejpg"


def test_channel_picture_ids_cannot_reach_other_files(env):
    assert env.client.get("/api/admin/channel-pictures/..%2Fkidtube.db").status_code == 404
    assert env.client.get("/api/admin/channel-pictures", params={"ids": "../x,ok_id_123"}).json() == {"ready": []}


# ---- named jobs and activity (ADR 0032) ----------------------------------------------------------------------------


def test_jobs_run_by_hand_and_are_recorded(env):
    reg = env.app.state.registry
    names = [j["name"] for j in env.client.get("/api/admin/background-jobs").json()["jobs"]]
    assert "channels" in names and "import-read" not in names
    assert reg.start_job("ytdlp", wait=True)
    hist = env.client.get("/api/admin/background-jobs/ytdlp/history").json()
    assert hist[0]["state"] == "done" and hist[0]["result"] == "yt-dlp updated from 2026.01.01 to 2026.02.02"
    v = env.client.get("/api/admin/background-jobs").json()["ytdlp"]
    assert v["have"] == v["newest"] == "2026.02.02"  # updated: nothing left to offer


def test_switched_off_jobs_refuse_to_run(env):
    r = env.client.post("/api/admin/background-jobs/ai-picks/run")
    assert r.status_code == 409 and "AI" in r.json()["detail"]


def test_pausing_scheduled_jobs_stops_them_coming_due(env):
    reg = env.app.state.registry
    assert reg.due(time.time() + 10**6)
    env.client.put("/api/admin/background-jobs/pause", json={"checks_paused": True})
    assert reg.due(time.time() + 10**6) == []


def test_activity_shows_failed_downloads(env):
    env.fake.fail = True
    env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=zz"]})
    env.run_jobs()
    a = env.client.get("/api/admin/activity").json()
    assert a["failed"] == 1 and a["running"] == [] and a["downloads"] == []


# ---- import (ADR 0035) ---------------------------------------------------------------------------------------------


def test_links_and_handles_come_out_of_any_pasted_text():
    text = ("Approved: https://www.youtube.com/@trains, youtube.com/watch?v=abcdefghijk.\n"
            "also @blippi and https://youtu.be/xyz12345678 and https://example.com/no")
    assert importer.parse_links(text) == [
        "https://www.youtube.com/@trains", "https://youtube.com/watch?v=abcdefghijk",
        "https://youtu.be/xyz12345678", "https://www.youtube.com/@blippi",
    ]


def test_takeout_csvs_give_channels_or_videos():
    subs = "﻿Channel Id,Channel Url,Channel Title\nUC1,http://www.youtube.com/channel/UC1,Trains\n"
    assert importer.parse_takeout(subs) == ["https://www.youtube.com/channel/UC1"]
    plist = "Video ID,Playlist Video Creation Timestamp\nabcdefghijk,2024-01-01\nbad,2024\n"
    assert importer.parse_takeout(plist) == ["https://www.youtube.com/watch?v=abcdefghijk"]


def history_html(*video_ids: str, advert: str = "") -> str:
    """A Takeout watch-history.html as YouTube Kids writes it: one cell per watch, only the link."""
    def cell(vid: str, caption: str = "") -> str:
        link = f"https://www.youtube.com/watch?v={vid}"
        return ('<div class="outer-cell mdl-cell"><div class="content-cell">Watched\xa0'
                f'<a href="{link}">{link}</a><br>Nov 22, 2026, 6:17:59 PM CST<br></div>'
                f'<div class="content-cell mdl-typography--caption"><b>Products:</b> YouTube{caption}</div></div>')
    cells = [cell(v) for v in video_ids] + ([cell(advert, "<b>Details:</b> From Google Ads")] if advert else [])
    return "<!DOCTYPE html><html><head><title>My Activity History</title></head><body>" + "".join(cells) + "</body></html>"


def test_watch_history_counts_each_video_and_leaves_adverts_out():
    html = history_html("aaaaaaaaaaa", "bbbbbbbbbbb", "aaaaaaaaaaa", "aaaaaaaaaaa", advert="ccccccccccc")
    assert importer.is_history(html) and not importer.is_history("Channel Id,Channel Url\n")
    assert importer.parse_history(html) == {"aaaaaaaaaaa": 3, "bbbbbbbbbbb": 1}
    as_json = json.dumps([
        {"title": "Watched a video", "titleUrl": "https://www.youtube.com/watch?v=aaaaaaaaaaa"},
        {"title": "Watched a video", "titleUrl": "https://www.youtube.com/watch?v=aaaaaaaaaaa"},
        {"title": "Watched an advert", "titleUrl": "https://www.youtube.com/watch?v=ccccccccccc",
         "details": [{"name": "From Google Ads"}]},
        {"title": "Visited YouTube Music"},
    ])
    assert importer.parse_history(as_json) == {"aaaaaaaaaaa": 2}
    assert importer.parse_history("[not json") == {}


def test_takeout_files_merge_across_kids_and_keep_the_most_watched():
    subs = "Channel Id,Channel Url,Channel Title\nUC1,http://www.youtube.com/channel/UC1,Trains\n"
    one = history_html(*["aaaaaaaaaaa"] * 3, *["bbbbbbbbbbb"] * 2)
    two = history_html(*["aaaaaaaaaaa"] * 4, "ddddddddddd")
    links, note = importer.from_files([(subs, [1]), (one, [1]), (subs, [2]), (two, [2])], min_watches=3)
    assert [(link.url.rsplit("/", 1)[-1], link.watches, link.profile_ids) for link in links] == [
        ("UC1", 0, (1, 2)), ("watch?v=aaaaaaaaaaa", 7, (1, 2))]
    assert note == "The watch history has 3 different videos; 1 of them were watched 3 times or more."
    assert importer.from_files([("﻿Channel Id\n", [])]) == ([], "")


def test_import_of_a_watch_history_groups_videos_under_their_channel(env):
    sam, alex = kids(env)
    files = [{"text": history_html(*["wwwwwwwwww1"] * 3, *["wwwwwwwwww2"] * 5, "wwwwwwwwww3"),
              "profile_ids": [sam, 999]}]
    r = env.client.post("/api/admin/import", json={"source": "takeout", "files": files, "min_watches": 3})
    assert r.status_code == 200 and r.json()["links"] == 2
    iid = r.json()["id"]
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "review")
    d = env.client.get(f"/api/admin/import/{iid}").json()
    assert "3 different videos; 2 of them" in d["import"]["note"] and d["progress"] == {"total": 3, "done": 3}
    vids = [x for x in d["rows"] if x["kind"] == "video"]
    chan = next(x for x in d["rows"] if x["kind"] == "channel")
    assert [(v["external_id"], v["watches"], v["profile_ids"]) for v in vids] == [
        ("wwwwwwwwww2", 5, [sam]), ("wwwwwwwwww1", 3, [sam])]  # most watched first; the unknown kid is dropped
    # The channel was never in the file: it comes from the videos, with their watches, and is not looked up.
    assert (chan["external_id"], chan["title"], chan["watches"], chan["video_count"], chan["profile_ids"]) == (
        "chan1", "Trains", 8, 0, [sam])
    assert chan["url"] == "https://www.youtube.com/channel/chan1" and chan["has_pic"]
    # "Just the videos": the channel row is skipped, the videos are approved for the kid whose file it was.
    choices = [{"row_id": chan["id"], "action": "skip"}] + [
        {"row_id": v["id"], "action": "approve", "profile_ids": v["profile_ids"]} for v in vids]
    assert env.client.post(f"/api/admin/import/{iid}/apply", json={"choices": choices}).status_code == 200
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "done")
    with env.db.conn() as c:
        got = c.execute(
            "SELECT i.external_id, i.approval, count(a.profile_id) n, max(a.profile_id) p FROM items i "
            "LEFT JOIN assignments a ON a.item_id = i.id GROUP BY i.id ORDER BY i.external_id").fetchall()
        subs = c.execute("SELECT count(*) FROM subscriptions").fetchone()[0]
        whole_channel = c.execute("SELECT count(*) FROM assignments WHERE container_id IS NOT NULL").fetchone()[0]
    assert [tuple(g) for g in got] == [("wwwwwwwwww1", "approved", 1, sam), ("wwwwwwwwww2", "approved", 1, sam)]
    assert subs == 0 and whole_channel == 0


def test_a_subscribed_channel_takes_the_watches_of_its_videos(env):
    subs = "Channel Id,Channel Url,Channel Title\nchan1,http://www.youtube.com/channel/chan1,Trains\n"
    files = [{"text": subs}, {"text": history_html(*["wwwwwwwwww1"] * 3)}]
    iid = env.client.post("/api/admin/import", json={"source": "takeout", "files": files}).json()["id"]
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "review")
    rows = env.client.get(f"/api/admin/import/{iid}").json()["rows"]
    chans = [x for x in rows if x["kind"] == "channel"]
    assert len(chans) == 1 and (chans[0]["watches"], chans[0]["video_count"]) == (3, 3)


def test_import_reads_reviews_and_applies(env):
    sam, alex = kids(env)
    r = env.client.post("/api/admin/import", json={
        "source": "paste", "text": "https://www.youtube.com/@trains\nhttps://www.youtube.com/watch?v=v1"})
    iid = r.json()["id"]
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "review")
    rows = env.client.get(f"/api/admin/import/{iid}").json()["rows"]
    chan = next(x for x in rows if x["kind"] == "channel")
    vid = next(x for x in rows if x["kind"] == "video")
    assert chan["title"] == "Trains" and chan["video_count"] == 3
    choices = [
        {"row_id": chan["id"], "action": "approve", "profile_ids": [sam]},
        {"row_id": vid["id"], "action": "approve", "profile_ids": [alex]},
    ]
    assert env.client.post(f"/api/admin/import/{iid}/apply", json={"choices": choices}).status_code == 200
    wait_for(lambda: env.client.get(f"/api/admin/import/{iid}").json()["import"]["state"] == "done")
    with env.db.conn() as c:
        item = c.execute("SELECT approval FROM items WHERE external_id = 'v1'").fetchone()
        chan_assigned = c.execute(
            "SELECT count(*) FROM assignments a JOIN containers c ON c.id = a.container_id "
            "WHERE c.external_id = 'chan1' AND a.profile_id = ?", (sam,)).fetchone()[0]
        subs = c.execute("SELECT count(*) FROM subscriptions").fetchone()[0]
    assert item["approval"] == "approved" and chan_assigned == 1 and subs == 0  # "approve only" downloads nothing


def test_import_of_nothing_is_refused(env):
    r = env.client.post("/api/admin/import", json={"source": "paste", "text": "no links here"})
    assert r.status_code == 422


# ---- avatars (ADR 0036) --------------------------------------------------------------------------------------------


def test_each_child_gets_a_different_character_and_colour(env):
    kids(env)
    ps = env.client.get("/api/admin/profiles").json()
    assert ps[0]["avatar"] != ps[1]["avatar"] and ps[0]["avatar_color"] != ps[1]["avatar_color"]
    assert ps[0]["avatar_url"].startswith("/avatars/") and env.client.get(ps[0]["avatar_url"]).status_code == 200


def test_avatar_choices_are_checked_and_uploads_work(env):
    sam, _ = kids(env)
    assert env.client.patch(f"/api/admin/profiles/{sam}", json={"avatar": "../x"}).status_code == 422
    assert env.client.patch(f"/api/admin/profiles/{sam}", json={"avatar_color": "plaid"}).status_code == 422
    assert env.client.post(f"/api/admin/profiles/{sam}/avatar-image", content=b"<svg/>",
                           headers={"Content-Type": "image/svg+xml"}).status_code == 415
    r = env.client.post(f"/api/admin/profiles/{sam}/avatar-image", content=b"\x89PNG....",
                        headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    tv = env.pair()["client"]
    url = next(p for p in tv.get("/api/tv/v1/profiles").json() if p["id"] == sam)["avatar_url"]
    assert url.startswith("/avatars/custom/") and tv.get(url).content == b"\x89PNG...."
    assert env.client.get(url).status_code == 200  # the parents' page
    from fastapi.testclient import TestClient

    assert TestClient(env.app).get(url).status_code == 401  # anyone else


# ---- AI (ADR 0034) -------------------------------------------------------------------------------------------------


class FakeOpenRouter:
    def __init__(self, answer: dict):
        self.answer, self.sent = answer, []

    def __call__(self, method, url, key, body=None, timeout=60):
        if url.endswith("/key"):
            return {"data": {"label": "test"}}
        self.sent.append(body)
        content = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)  # a str: the raw reply
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.001}}


def ai_on(env, monkeypatch, answer):
    fake = FakeOpenRouter(answer)
    monkeypatch.setattr(openrouter, "_http", fake)
    r = env.client.put("/api/admin/ai", json={"key": "sk-or-test-SECRET", "enabled": True})
    assert r.status_code == 200 and "SECRET" not in r.text
    return fake


def test_the_key_never_comes_back_to_the_page(env, monkeypatch):
    ai_on(env, monkeypatch, {})
    body = env.client.get("/api/admin/ai").json()
    assert body["key_saved"] is True and "sk-or" not in json.dumps(body)


def test_picks_only_reorder_visible_videos_and_never_name_the_boys(env, monkeypatch):
    sam, alex = kids(env)
    env.client.patch(f"/api/admin/profiles/{sam}", json={"birthday": "2022-03-01"})
    r = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v={v}" for v in ("a", "b", "c", "d", "e")],
                                                "approve": True})
    ids = r.json()["added"]
    hidden = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=h"]}).json()["added"][0]
    env.run_jobs()
    order = [ids[3], 99999, hidden, ids[0], ids[1], ids[2], ids[4]]  # an unknown id and an unapproved one
    fake = ai_on(env, monkeypatch, {"order": order})
    assert env.app.state.registry.start_job("ai-picks", wait=True)
    sent = json.dumps(fake.sent)
    assert "Sam" not in sent and "Alex" not in sent and "2022" not in sent and "Child A" in sent
    tv = env.pair()["client"]
    rows = tv.get("/api/tv/v1/home", params={"profile_id": sam}).json()["rows"]
    picked = next(r for r in rows if r["id"] == "picked")
    assert [c["id"] for c in picked["cards"]] == [ids[3], ids[0], ids[1], ids[2], ids[4]]


def test_picks_ask_again_when_the_model_thought_past_its_room(env, monkeypatch):
    """2026-11-24: Haiku thought for ~900 hidden tokens; when that ran past max_tokens the answer was empty and the
    job failed without asking again. Now thinking is asked off, and an empty cut-off answer gets the second try."""
    sam, alex = kids(env)
    ids = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v={v}" for v in "abcd"],
                                                  "approve": True}).json()["added"]
    env.run_jobs()
    fake = ai_on(env, monkeypatch, {"order": ids})
    replies = iter([{"content": "", "finish_reason": "length"}])

    def first_empty(method, url, key, body=None, timeout=60):
        if body is not None and not url.endswith("/key"):
            r = next(replies, None)
            if r:
                fake.sent.append(body)
                return {"choices": [{"message": {"content": r["content"]}, "finish_reason": r["finish_reason"]}],
                        "usage": {"completion_tokens": 1200}}
        return fake(method, url, key, body, timeout)

    monkeypatch.setattr(openrouter, "_http", first_empty)
    env.client.patch(f"/api/admin/profiles/{alex}", json={"picks_on": False})  # one profile: one row
    assert env.app.state.registry.start_job("ai-picks", wait=True)
    assert all(b.get("reasoning") == {"enabled": False} for b in fake.sent)
    assert len(fake.sent) == 2  # the empty answer, then the one that worked
    with env.app.state.db.conn() as c:
        got = json.loads(c.execute("SELECT item_ids FROM picks WHERE profile_id = ?", (sam,)).fetchone()[0])
    assert got == ids


def test_a_model_that_must_think_is_asked_again_without_the_switch(env, monkeypatch):
    fake = ai_on(env, monkeypatch, {"ok": True})

    def refuses(method, url, key, body=None, timeout=60):
        if body is not None and "reasoning" in body:
            fake.sent.append(body)
            return {"error": {"message": "Reasoning is mandatory for this endpoint and cannot be disabled."}}
        return fake(method, url, key, body, timeout)

    monkeypatch.setattr(openrouter, "_http", refuses)
    assert env.client.post("/api/admin/ai/try").status_code == 200
    assert [("reasoning" in b) for b in fake.sent] == [True, False]


def test_the_row_falls_back_and_can_be_switched_off(env, monkeypatch):
    sam, _ = kids(env)
    env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=a"], "approve": True})
    env.run_jobs()
    tv = env.pair()["client"]
    home = lambda: [r["id"] for r in tv.get("/api/tv/v1/home", params={"profile_id": sam}).json()["rows"]]
    assert "picked" not in home()  # AI off: no row at all
    ai_on(env, monkeypatch, {"order": []})
    assert "picked" in home()  # on, nothing cached yet: the rule-based order fills it
    env.client.patch(f"/api/admin/profiles/{sam}", json={"picks_on": False})
    assert "picked" not in home()


def test_the_monthly_cap_stops_ai_calls(env, monkeypatch):
    ai_on(env, monkeypatch, {"ok": True})
    env.client.put("/api/admin/ai", json={"cap_usd": 0.0015})
    assert env.client.post("/api/admin/ai/try").status_code == 200
    assert env.client.post("/api/admin/ai/try").status_code == 200  # 0.002 spent now
    r = env.client.post("/api/admin/ai/try")
    assert r.status_code == 502 and "cap" in r.json()["detail"]


def test_suggestions_are_looked_up_and_added_ones_leave_the_inbox(env, monkeypatch):
    kids(env)
    ai_on(env, monkeypatch, {"suggestions": [
        {"for": ["Child B"], "kind": "channel", "search": "gentle trains", "reason": "He likes vehicles."},
        {"for": ["Child A"], "kind": "video", "search": "train song", "reason": "Short and calm."},
    ]})
    assert env.app.state.registry.start_job("ai-suggest", wait=True)
    got = {s["kind"]: s for s in env.client.get("/api/admin/suggestions").json()}
    assert got["channel"]["external_id"] == "chan1" and got["channel"]["reason"] == "He likes vehicles."
    assert got["video"]["external_id"] == "s1"
    env.client.post("/api/admin/add", json={"urls": [got["video"]["url"]], "approve": True})
    left = [s["kind"] for s in env.client.get("/api/admin/suggestions").json()]
    assert left == ["channel"]


def test_parents_page_files_are_checked_every_load(env):
    """Without Cache-Control the browser kept yesterday's app.js after a deploy (2026-11-23, the Jobs page fix)."""
    for path in ("/admin/", "/admin/app.js"):
        r = env.client.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"
        assert env.client.get(path, headers={"If-None-Match": r.headers["etag"]}).status_code == 304


def test_search_show_more_asks_for_a_bigger_top(env):
    """"Show more" under YouTube results (2026-11-23): `limit` is the size of the top asked for, kept in 1..300."""
    assert [v["external_id"] for v in env.client.get("/api/admin/search", params={"q": "trains"}).json()] == ["s1", "s2"]
    assert [v["external_id"] for v in env.client.get("/api/admin/search", params={"q": "trains", "limit": 1}).json()] == ["s1"]
    seen = []
    env.fake.search = lambda q, count=15: seen.append(count) or []
    env.client.get("/api/admin/search", params={"q": "trains", "limit": 5000})
    env.client.get("/api/admin/search", params={"q": "trains", "limit": -3})
    assert seen == [300, 1]


def test_jobs_page_lists_every_running_job_hidden_ones_too(env):
    """Jobs › Running now (2026-11-23): an import runs as a hidden job and must still show while it runs."""
    import threading

    from app.jobs_registry import Job

    reg, go_on = env.app.state.registry, threading.Event()

    def slow(run):
        run.note("Reading row 3 of 10")
        go_on.wait(5)
        return "done"

    reg.jobs["test-hidden"] = Job("test-hidden", "Reading an import", "", slow, stoppable=True, listed=False)
    assert reg.start_job("test-hidden", by_hand=True)
    body = env.client.get("/api/admin/background-jobs").json()
    running = {r["name"]: r for r in body["running"]}
    assert running["test-hidden"]["note"] == "Reading row 3 of 10" and running["test-hidden"]["listed"] is False
    assert running["test-hidden"]["stoppable"] is True and body["now"] >= running["test-hidden"]["started_at"]
    assert "test-hidden" not in [j["name"] for j in body["jobs"]]  # still not a card with Run now
    go_on.set()
    wait_for(lambda: not env.client.get("/api/admin/background-jobs").json()["running"])


def test_a_reply_cut_off_mid_list_still_gives_a_row(env, monkeypatch):
    """2026-11-24: after a big import the reply hit max_tokens and the job failed with "did not answer in JSON"."""
    sam, _ = kids(env)
    ids = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v={v}" for v in ("a", "b", "c")],
                                                  "approve": True}).json()["added"]
    env.run_jobs()
    ai_on(env, monkeypatch, f'{{"order": [{ids[2]}, 99999, {ids[0]}, {ids[1]}')  # stops mid-list, no closing brackets
    assert env.app.state.registry.start_job("ai-picks", wait=True)
    with env.db.conn() as c:  # the ids it named before it stopped, in its order; 99999 was never offered
        assert json.loads(c.execute("SELECT item_ids FROM picks WHERE profile_id = ?", (sam,)).fetchone()[0]) == [ids[2], ids[0], ids[1]]
    fake = ai_on(env, monkeypatch, "Sorry, I can't help with that.")  # nothing usable twice: still an error
    assert env.app.state.registry.start_job("ai-picks", wait=True)
    with env.db.conn() as c:
        assert c.execute("SELECT state FROM job_runs WHERE job = 'ai-picks' ORDER BY id DESC").fetchone()[0] == "failed"
    assert len(fake.sent) == 2  # asked once more before giving up


def test_a_failed_automatic_ytdlp_update_keeps_the_button(env, monkeypatch):
    from app.downloads import ytdlp_update

    def broken(data_dir):
        raise RuntimeError("pip failed: no network")

    monkeypatch.setattr(ytdlp_update, "update", broken)
    env.app.state.registry.start_job("ytdlp", wait=True)
    run = env.client.get("/api/admin/background-jobs/ytdlp/history").json()[0]
    assert run["state"] == "failed" and "no network" in (run.get("error") or run.get("result") or "")
    v = env.client.get("/api/admin/background-jobs").json()["ytdlp"]
    assert (v["have"], v["newest"]) == ("2026.01.01", "2026.02.02")  # the page still offers Update yt-dlp


def test_library_videos_can_come_a_to_z(env):
    ids = env.client.post("/api/admin/add", json={"urls": [f"https://example.test/watch?v={v}" for v in ("c", "a", "b")],
                                                  "approve": True}).json()["added"]
    by = lambda order: [r["title"] for r in env.client.get("/api/admin/items", params={"approval": "approved", "order": order}).json()]
    assert by("title") == ["Video a", "Video b", "Video c"]
    assert by("added") == ["Video b", "Video a", "Video c"]  # newest first, as before


def test_parents_page_works_under_a_path_prefix(env):
    """Served as a Home Assistant ingress panel (/api/ingress/colors/...), absolute URLs went to HA's root (2026-11-26).
    The root redirect and every URL the page asks for must be relative."""
    import re
    from pathlib import Path

    r = env.client.get("/", follow_redirects=False)
    assert r.headers["location"] == "admin/"
    js = (Path(__file__).resolve().parents[1] / "app" / "static" / "admin" / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"""(fetch\(|src: )\s*[\"'`]/(?!/)""", js)
    assert not re.search(r"""[\"'`]/api/""", js)
