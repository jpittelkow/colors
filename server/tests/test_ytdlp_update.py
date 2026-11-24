"""yt-dlp can be updated from the page without a new image (2026-11-24). pip and PyPI are faked here; the swap and
the "newer wins" rule are real."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.downloads import ytdlp_update as up


def fake_ytdlp(folder: Path, version: str) -> None:
    (folder / "yt_dlp").mkdir(parents=True, exist_ok=True)
    (folder / "yt_dlp" / "version.py").write_text(f"__version__ = '{version}'\n", encoding="utf-8")


@pytest.fixture
def path(monkeypatch, tmp_path):
    image = tmp_path / "site-packages"
    fake_ytdlp(image, "2026.11.01")
    monkeypatch.setattr(sys, "path", [str(image)])
    monkeypatch.setattr(up, "_dir", None)
    return tmp_path


def test_a_newer_copy_in_the_data_folder_wins_and_an_older_one_does_not(path):
    data = path / "data"
    fake_ytdlp(data / "pylib", "2026.11.23")
    assert up.activate(data) == "2026.11.23" and sys.path[0] == str(data / "pylib")
    sys.path.remove(str(data / "pylib"))
    fake_ytdlp(data / "pylib", "2026.10.01")  # a newer image came later: its yt-dlp is used, not the old copy
    assert up.activate(data) is None and str(data / "pylib") not in sys.path


def test_update_installs_beside_then_swaps_and_reloads(path, monkeypatch):
    data = path / "data"
    fake_ytdlp(data / "pylib", "2026.11.10")
    calls = []
    monkeypatch.setattr(up, "loaded_version", lambda: "2026.11.10" if not calls else "2026.11.23")
    monkeypatch.setattr(up, "newest", lambda: ("2026.11.23", "0.3.2"))
    monkeypatch.setattr(up, "_pip", lambda target, pkgs: (calls.append(pkgs), fake_ytdlp(target, "2026.11.23")))
    monkeypatch.setattr(up, "_reload", lambda: calls.append("reload"))
    assert up.update(data) == {"updated": True, "from": "2026.11.10", "version": "2026.11.23"}
    assert calls == [["yt-dlp==2026.11.23", "yt-dlp-ejs==0.3.2"], "reload"]
    assert up._version_in(data / "pylib") == "2026.11.23"
    assert not (data / "pylib.new").exists() and not (data / "pylib.old").exists()


def test_a_failed_install_leaves_the_working_copy_alone(path, monkeypatch):
    data = path / "data"
    fake_ytdlp(data / "pylib", "2026.11.10")
    monkeypatch.setattr(up, "loaded_version", lambda: "2026.11.10")
    monkeypatch.setattr(up, "newest", lambda: ("2026.11.23", None))
    monkeypatch.setattr(up, "_pip", lambda target, pkgs: (_ for _ in ()).throw(RuntimeError("pip failed: no network")))
    with pytest.raises(RuntimeError):
        up.update(data)
    assert up._version_in(data / "pylib") == "2026.11.10"


def test_nothing_to_do_when_already_newest(path, monkeypatch):
    monkeypatch.setattr(up, "loaded_version", lambda: "2026.11.23")
    monkeypatch.setattr(up, "newest", lambda: ("2026.11.23", None))
    assert up.update(path / "data")["updated"] is False


def test_the_ejs_pin_is_read_from_pypi():
    m = up.EJS_RE.match('yt-dlp-ejs==0.3.2; extra == "default"')
    assert m and m.group(1) == "0.3.2"
