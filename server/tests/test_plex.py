"""Plex as a source (ADR 0008), with Plex itself faked."""
from __future__ import annotations

from app.sources import plex

SHOW = {"ratingKey": "100", "type": "show", "title": "Puddle Pals"}
EPISODES = [
    {"ratingKey": "101", "type": "episode", "title": "The Big Boat", "parentIndex": 1, "index": 1, "duration": 660000,
     "Media": [{"videoCodec": "h264", "audioCodec": "aac", "height": 1080, "Part": [{"key": "/library/parts/9/1/f.mkv"}]}]},
    {"ratingKey": "102", "type": "episode", "title": "Rainy Day", "parentIndex": 1, "index": 2, "duration": 650000,
     "Media": [{"videoCodec": "hevc", "audioCodec": "dca", "height": 2160, "Part": [{"key": "/library/parts/9/2/f.mkv"}]}]},
]


def fake_get(db, path, **params):
    if path == "/":
        return {"friendlyName": "Home server"}
    if path == "/library/metadata/100":
        return {"Metadata": [SHOW]}
    if path == "/library/metadata/100/allLeaves":
        return {"Metadata": EPISODES}
    if path == "/library/sections":
        return {"Directory": [{"key": "2", "title": "TV Shows", "type": "show"}, {"key": "9", "title": "Music", "type": "artist"}]}
    raise AssertionError(path)


def test_allow_a_show(env, monkeypatch):
    monkeypatch.setattr(plex, "_get", fake_get)
    env.db.set_setting("plex_url", "http://plex.test:32400")
    env.db.set_setting("plex_token", "secret-plex-token")
    sam = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    assert env.client.get("/api/admin/plex/sections").json() == [{"key": "2", "title": "TV Shows", "type": "show"}]
    r = env.client.post("/api/admin/plex/allow", json={"rating_key": "100"}).json()
    assert len(r["containers"]) == 1
    st = env.client.get("/api/admin/plex").json()
    assert st["connected"] is True and st["allowed"][0]["ready"] == 1 and st["allowed"][0]["unplayable"] == 1
    assert "DCA sound" in st["unplayable"][0]["play_note"] and "4K video" in st["unplayable"][0]["play_note"]

    tv = env.pair()["client"]
    home = tv.get("/api/tv/v1/home", params={"profile_id": sam}).json()
    titles = [c["title"] for r in home["rows"] if r["id"] == "new" for c in r["cards"]]
    assert titles == ["S1E1 The Big Boat"]  # the unplayable episode never reaches the TV
    play = tv.post("/api/tv/v1/play", json={"profile_id": sam, "item_id": home["rows"][0]["cards"][0]["id"]}).json()
    assert "secret-plex-token" not in str(play) and "/library/parts" not in str(play)

    # allowing again is idempotent; removing it stops showing it
    env.client.post("/api/admin/plex/allow", json={"rating_key": "100"})
    assert len(env.client.get("/api/admin/plex").json()["allowed"]) == 1
    env.client.delete(f"/api/admin/plex/containers/{r['containers'][0]}")
    assert tv.get("/api/tv/v1/home", params={"profile_id": sam}).json()["rows"] == []


def test_search_covers_every_section_and_collections(env, monkeypatch):
    calls = []

    def fake(db, path, **params):
        calls.append((path, params))
        if path == "/library/sections":
            return {"Directory": [{"key": "1", "title": "Movies", "type": "movie"},
                                  {"key": "2", "title": "TV", "type": "show"}]}
        if path == "/library/sections/2/all":
            return {"Metadata": [{"ratingKey": "50", "title": "Bluey", "type": "show", "leafCount": 150},
                                 {"ratingKey": "51", "title": "A Bluey Special", "type": "show"}]}
        if path == "/library/sections/1/collections":
            return {"Metadata": [{"ratingKey": "50", "title": "Bluey", "type": "collection"}]}  # same key: once
        return {}

    monkeypatch.setattr(plex, "_get", fake)
    r = env.client.get("/api/admin/plex/search", params={"q": "bluey"}).json()
    assert [m["rating_key"] for m in r] == ["50", "51"]  # starts-with first, no duplicates
    assert r[0]["section"] == "TV"
    assert all(p.get("title") == "bluey" for path, p in calls if path != "/library/sections")
    assert env.client.get("/api/admin/plex/search", params={"q": "b"}).status_code == 422
    assert env.client.get("/api/admin/plex/poster/..%2Fx").status_code == 404
