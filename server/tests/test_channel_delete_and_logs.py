"""Subscribing from a channel saved without an address, "Unsubscribe and delete all", readable 422s, and the
rotating log file (2026-11-24)."""
from __future__ import annotations

import logging

from app import logs
from app.downloads import jobs as jobs_mod


def _channel_without_url(env) -> int:
    """A channel as older imports left it: no address saved."""
    env.client.post("/api/admin/profiles", json={"name": "Sam"})
    item = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=one"], "approve": True}).json()["added"][0]
    with env.db.conn() as c:
        cid = c.execute("SELECT container_id FROM items WHERE id = ?", (item,)).fetchone()[0]
        c.execute("UPDATE containers SET url = '', external_id = 'UCtrains000000000000000' WHERE id = ?", (cid,))
    return cid


def test_subscribing_from_a_channel_page_without_an_address_works(env):
    cid = _channel_without_url(env)
    ch = env.client.get(f"/api/admin/channels/{cid}").json()["channel"]
    assert ch["url"] == "https://www.youtube.com/channel/UCtrains000000000000000"  # built from its id
    r = env.client.post("/api/admin/subscribe", json={"url": "", "container_id": cid, "rules": {"mode": "new"}})
    assert r.status_code == 200, r.text


def test_new_channels_save_their_address():
    assert jobs_mod.channel_url("UCabc") == "https://www.youtube.com/channel/UCabc"
    assert jobs_mod.channel_url("UCabc", "https://www.youtube.com/@abc") == "https://www.youtube.com/@abc"
    assert jobs_mod.channel_url("unknown:Somebody") == ""


def test_subscribe_with_no_address_at_all_says_so(env):
    r = env.client.post("/api/admin/subscribe", json={"url": ""})
    assert r.status_code == 400 and "no YouTube address" in r.json()["detail"]


def test_a_bad_value_names_the_setting(env):
    r = env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains", "rules": {"daily_cap": 500}})
    assert r.status_code == 422
    assert r.json()["detail"]["message"].startswith("Check “Most downloads a day”:")


def test_unsubscribe_and_delete_all(env, tmp_path):
    env.client.post("/api/admin/profiles", json={"name": "Sam"})
    rules = {"mode": "last", "last_n": 2, "daily_cap": 10}
    r = env.client.post("/api/admin/subscribe", json={"url": "https://www.youtube.com/@trains", "rules": rules}).json()
    cid = r["container_id"]
    env.run_jobs()  # both download
    with env.db.conn() as c:
        files = [env.cfg.library_dir / row[0] for row in c.execute("SELECT file_path FROM items WHERE container_id = ?", (cid,))]
    assert files and all(f.exists() for f in files)
    out = env.client.delete(f"/api/admin/channels/{cid}").json()
    assert out["videos"] == len(files)
    assert not any(f.exists() for f in files)
    with env.db.conn() as c:
        assert c.execute("SELECT count(*) FROM containers WHERE id = ?", (cid,)).fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM subscriptions WHERE container_id = ?", (cid,)).fetchone()[0] == 0
    assert env.client.delete(f"/api/admin/channels/{cid}").status_code == 404


def test_log_file_rotates_every_few_days(tmp_path):
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        path = logs.setup(tmp_path)
        fh = next(h for h in root.handlers if getattr(h, "colors_file", False))
        assert path == tmp_path / "logs" / "colors.log" and fh.interval == logs.ROTATE_DAYS * 86400
        assert fh.backupCount == logs.KEEP
        logging.getLogger("kidtube.test").warning("hello from the test")
        fh.flush()
        assert "hello from the test" in path.read_text(encoding="utf-8")
    finally:
        for h in list(root.handlers):
            if h not in before:
                root.removeHandler(h)
                h.close()
        for name in ("uvicorn.access", "uvicorn.error"):
            for h in list(logging.getLogger(name).handlers):
                logging.getLogger(name).removeHandler(h)
                h.close()
