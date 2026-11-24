"""Home Assistant API (ADR 0020) and the storage cap (ADR 0005)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.downloads import jobs

A = "/api/automation/v1"


def test_key_required_and_actions(env):
    pid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    ha = TestClient(env.app)
    assert ha.get(f"{A}/status").status_code == 401  # no key exists yet
    key = env.client.post("/api/admin/automation/key").json()["key"]
    assert ha.get(f"{A}/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ha.headers["Authorization"] = f"Bearer {key}"
    st = ha.get(f"{A}/status").json()
    assert st["profiles"][0]["name"] == "Sam" and st["profiles"][0]["minutes_left"] is None

    st = ha.post(f"{A}/profiles/{pid}/limit", json={"minutes": 20}).json()
    assert 19.5 <= st["profiles"][0]["minutes_left"] <= 20
    st = ha.post(f"{A}/all/lock").json()
    assert st["profiles"][0]["open"] is False
    assert ha.post(f"{A}/profiles/{pid}/explode").status_code == 404

    # a new key stops the old one, and the admin cookie is not a key
    env.client.post("/api/admin/automation/key")
    assert ha.get(f"{A}/status").status_code == 401
    assert env.client.get(f"{A}/status").status_code == 401


def test_vacation_uses_weekend_allowance(env):
    pid = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    env.client.put(f"/api/admin/limits/{pid}", json={"weekday_min": 10, "weekend_min": 90})
    env.client.post("/api/admin/automation/vacation", json={"on": True})
    kids = env.client.get("/api/admin/kids").json()
    assert kids[0]["time"]["daily_s"] == 90 * 60


def test_storage_cap_pauses_downloads(env):
    env.client.put("/api/admin/settings", json={"storage_cap_gb": 1})
    assert jobs.storage_full(env.db, env.cfg.library_dir) is False
    big = env.cfg.library_dir / "big.bin"
    with open(big, "wb") as f:
        f.truncate(int(1.1e9))  # sparse file: no real disk used
    assert jobs.storage_full(env.db, env.cfg.library_dir) is True
    assert env.client.get("/api/admin/settings").json()["storage_full"] is True
    big.unlink()
