"""Evening out the volume (ADR 0041): the server measures each video once, the play answer carries the gain."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from app.downloads import loudness


def profile(env) -> int:
    return env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]


def add(env, *vids):
    urls = [f"https://example.test/watch?v={v}" for v in vids]
    ids = env.client.post("/api/admin/add", json={"urls": urls, "approve": True}).json()["added"]
    env.run_jobs()
    return ids


def test_gain_brings_a_video_to_the_target_within_limits():
    assert loudness.gain_db(-20.0) == 4.0          # quiet: up
    assert loudness.gain_db(-9.0) == -7.0          # loud: down
    assert loudness.gain_db(-40.0) == loudness.MOST_UP_DB    # very quiet: only so far up
    assert loudness.gain_db(0.0) == loudness.MOST_DOWN_DB
    assert loudness.gain_db(None) == 0.0           # not measured: as it is
    assert loudness.gain_db(-70.0) == 0.0          # no real sound: as it is


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_measure_reads_a_real_file(tmp_path):
    def tone(name, db):
        f = tmp_path / name
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                        "-f", "lavfi", "-i", "color=black:s=64x64:d=5", "-af", f"volume={db}dB", "-shortest", "-y", str(f)],
                       check=True)
        return loudness.measure(f)

    quiet, loud = tone("quiet.mp4", -20), tone("loud.mp4", -10)
    assert 9 < loud["lufs"] - quiet["lufs"] < 11 and loud["peak"] < 0
    with pytest.raises(RuntimeError):
        loudness.measure(tmp_path / "missing.mp4")


def test_the_job_measures_once_and_the_play_answer_carries_the_gain(env, monkeypatch):
    pid = profile(env)
    loud, broken = add(env, "loud", "broken")
    seen = []

    def fake_measure(path, ffmpeg="ffmpeg"):
        seen.append(path.name)
        if "broken" in str(path) or len(seen) > 2:
            raise RuntimeError("ffmpeg could not measure it")
        return {"lufs": -10.0, "peak": -0.5}

    monkeypatch.setattr(loudness, "measure", fake_measure)
    with env.db.conn() as c:  # the fake downloader's file names don't say which is which; make them
        for i, name in ((loud, "loud.mp4"), (broken, "broken.mp4")):
            c.execute("UPDATE items SET file_path = ? WHERE id = ?", (name, i))
    assert env.app.state.registry.start_job("loudness", wait=True)
    assert len(seen) == 2
    assert env.app.state.registry.start_job("loudness", wait=True)
    assert len(seen) == 2  # nothing measured twice, not even the one that failed
    assert env.client.get("/api/admin/settings").json()["loudness"] == {"videos": 2, "measured": 2}

    tv = env.pair()["client"]
    play = lambda i: tv.post("/api/tv/v1/play", json={"profile_id": pid, "item_id": i}).json()
    assert play(loud)["audio"] == {"gain_db": -6.0, "compress": True}
    assert play(broken)["audio"] == {"gain_db": 0.0, "compress": True}  # unreadable: as it is, still softened

    env.client.put("/api/admin/settings", json={"level_volume": False})
    assert play(loud)["audio"] is None
    assert env.client.get("/api/admin/settings").json()["level_volume"] is False
