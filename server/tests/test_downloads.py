"""The Downloads page: live progress, Stop, Try again, history (ADR 0032, revised) and the channel repair."""
from __future__ import annotations

from app.api import downloads as downloads_api
from app.downloads import jobs, progress
from app.downloads.ytdlp import Downloaded, VideoInfo


def add(env, *vids, approve=True) -> list[int]:
    urls = [f"https://example.test/watch?v={v}" for v in vids]
    return env.client.post("/api/admin/add", json={"urls": urls, "approve": approve}).json()["added"]


def job_of(env, item_id: int) -> int:
    with env.db.conn() as c:
        return c.execute("SELECT id FROM jobs WHERE item_id = ?", (item_id,)).fetchone()[0]


def test_a_waiting_download_can_be_stopped_and_tried_again(env):
    (item,) = add(env, "a")
    job = job_of(env, item)
    assert env.client.post(f"/api/admin/downloads/{job}/stop").json() == {"result": "stopped"}
    act = env.client.get("/api/admin/downloads/active").json()
    assert act["queued"] == [] and act["counts"]["stopped"] == 1 and act["counts"]["failed"] == 0
    assert env.client.post("/api/admin/downloads/retry-failed").json() == {"queued": 0}  # stopped is not failed
    env.client.post(f"/api/admin/downloads/{job}/retry")
    env.run_jobs()
    hist = env.client.get("/api/admin/downloads/history").json()
    assert hist["rows"][0]["status"] == "done" and hist["rows"][0]["bytes"] == 1000


def test_live_numbers_show_while_downloading_and_stop_ends_it(env):
    (item,) = add(env, "a")
    job = job_of(env, item)
    seen = {}

    def download(url, on_progress=lambda p: None):
        on_progress({"phase": "Downloading", "fraction": 0.42, "downloaded": 120, "total": 286, "speed": 4.2, "eta": 39})
        seen.update(downloads_api.live(env.db)[0])
        assert env.client.post(f"/api/admin/downloads/{job}/stop").json() == {"result": "stopping"}
        assert downloads_api.live(env.db)[0]["stopping"] is True
        on_progress({"phase": "Downloading", "fraction": 0.5})  # the next update notices the Stop
        raise AssertionError("the download should have been stopped")

    env.fake.download = download
    env.run_jobs()
    assert (seen["percent"], seen["phase"], seen["speed"], seen["eta"], seen["title"]) == (42.0, "Downloading", 4.2, 39, "Video a")
    row = env.client.get("/api/admin/downloads/history", params={"status": "stopped"}).json()["rows"][0]
    assert row["status"] == "stopped" and row["item_id"] == item
    assert progress.get(job) is None and downloads_api.live(env.db) == []
    assert env.client.get("/api/admin/activity").json()["failed"] == 0


def test_retry_all_failed_and_history_filters(env):
    env.fake.fail = True
    add(env, "a", "b")
    env.run_jobs()
    env.fake.fail = False
    add(env, "c")
    env.run_jobs()
    h = lambda **p: env.client.get("/api/admin/downloads/history", params=p).json()
    assert h()["total"] == 3 and h(status="failed")["total"] == 2 and h(status="done")["total"] == 1
    assert h(q="Video c")["total"] == 1 and h(q="Trains")["total"] == 3
    assert h(status="failed")["rows"][0]["error"] == "boom"
    assert env.client.post("/api/admin/downloads/retry-failed").json() == {"queued": 2}
    env.run_jobs()
    assert h(status="done")["total"] == 3


def test_a_video_filed_under_unknown_moves_to_its_channel(env):
    sam = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    real_look = env.fake.look

    def no_channel(url, limit=200):
        listing = real_look(url, limit)
        for v in listing.videos:
            v.channel_id, v.channel_title = "", ""
        return listing

    env.fake.look = no_channel  # YouTube gave no channel when the video was added
    (item,) = add(env, "a")
    with env.db.conn() as c:
        assert c.execute("SELECT external_id FROM containers").fetchone()[0] == "unknown:Unknown"
    env.fake.look = real_look
    env.run_jobs()  # the download itself knows the channel
    with env.db.conn() as c:
        rows = c.execute("SELECT external_id, title, url FROM containers").fetchall()
        seen = c.execute("SELECT count(*) FROM assignments WHERE profile_id = ? AND item_id = ?", (sam, item)).fetchone()[0]
    assert [tuple(r) for r in rows] == [("chan1", "Trains", "https://www.youtube.com/channel/chan1")]
    assert seen == 1


def test_the_repair_job_fixes_older_unknown_channels(env):
    with env.db.conn() as c:
        v = VideoInfo("old1", "https://example.test/watch?v=old1", "Old video")
        cid = jobs.ensure_channel(c, v)
        c.execute("INSERT INTO items (container_id, external_id, url, title, added_at) VALUES (?, 'old1', ?, 'Old', 0)",
                  (cid, v.url))
    assert jobs.repair_unknown(env.db, env.fake) == 1
    with env.db.conn() as c:
        assert [r[0] for r in c.execute("SELECT external_id FROM containers")] == ["chan1"]


def test_a_parent_can_change_how_often_a_job_runs(env):
    reg = env.app.state.registry
    assert env.client.put("/api/admin/background-jobs/channels/schedule", json={"minutes": 2}).status_code == 422
    assert env.client.put("/api/admin/background-jobs/channels/schedule", json={"minutes": 45}).status_code == 200
    job = next(j for j in env.client.get("/api/admin/background-jobs").json()["jobs"] if j["name"] == "channels")
    assert job["every_s"] == 45 * 60 and job["default_every_s"] == 600
    assert reg.every(reg.jobs["channels"]) == 2700
    assert env.client.put("/api/admin/background-jobs/import-read/schedule", json={"minutes": 45}).status_code == 404


def test_adding_looks_again_when_youtube_leaves_the_channel_out(env):
    real_look, calls = env.fake.look, []

    def flaky(url, limit=200):
        listing = real_look(url, limit)
        calls.append(url)
        if len(calls) == 1:
            listing.videos[0].channel_id = ""
        return listing

    env.fake.look = flaky
    add(env, "a")
    with env.db.conn() as c:
        assert [r[0] for r in c.execute("SELECT external_id FROM containers")] == ["chan1"]
    assert len(calls) == 2


def test_a_failed_download_tries_again_by_itself_before_it_counts_as_failed(env, monkeypatch):
    monkeypatch.setattr(jobs, "RETRY_DELAYS", (60, 300))
    env.fake.fail = True
    (item,) = add(env, "a")
    env.run_jobs()  # first try fails: it waits, it is not failed
    act = env.client.get("/api/admin/downloads/active").json()
    assert act["counts"]["failed"] == 0 and act["queued"][0]["error"] == "boom" and act["queued"][0]["retry_at"]
    assert env.client.get("/api/admin/activity").json()["retrying"] == 1
    assert jobs.run_one(env.db, env.fake, env.cfg.library_dir) is False  # not before its time
    with env.db.conn() as c:
        c.execute("UPDATE jobs SET retry_at = 1")  # its time has come
    env.fake.fail = False
    env.run_jobs()
    row = env.client.get("/api/admin/downloads/history").json()["rows"][0]
    assert row["status"] == "done" and row["attempts"] == 2 and row["error"] == ""


def test_three_failures_in_a_row_make_it_failed(env, monkeypatch):
    monkeypatch.setattr(jobs, "RETRY_DELAYS", (0, 0))
    env.fake.fail = True
    add(env, "a")
    env.run_jobs()
    with env.db.conn() as c:
        row = c.execute("SELECT state, attempts FROM jobs").fetchone()
    assert (row["state"], row["attempts"]) == ("failed", 3)
    job = env.client.get("/api/admin/downloads/history").json()["rows"][0]["job_id"]
    env.client.post(f"/api/admin/downloads/{job}/retry")  # a parent's Try again starts the count afresh
    with env.db.conn() as c:
        assert tuple(c.execute("SELECT state, attempts FROM jobs").fetchone()) == ("queued", 0)


def test_the_scheduled_retry_gives_up_after_six_tries(env):
    env.fake.fail = True
    add(env, "a")
    reg = env.app.state.registry
    for _ in range(9):
        env.run_jobs()
        reg.start_job("retry-failed", by_hand=False, wait=True)
    with env.db.conn() as c:
        row = c.execute("SELECT state, attempts FROM jobs").fetchone()
    assert (row["state"], row["attempts"]) == ("failed", 6)
    reg.start_job("retry-failed", by_hand=True, wait=True)  # a parent's Run now still tries
    with env.db.conn() as c:
        assert c.execute("SELECT state FROM jobs").fetchone()[0] == "queued"
