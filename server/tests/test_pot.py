"""The PO token helper's address goes to every YouTube call through yt-dlp's options (2026-11-24)."""
from pathlib import Path

from app.config import Config
from app.downloads.ytdlp import YtDlp


def test_the_helper_address_reaches_ytdlp_only_when_set(monkeypatch, tmp_path):
    with_helper = YtDlp(tmp_path, pot_url="http://192.168.1.10:4416")._opts(extract_flat=True)
    assert with_helper["extractor_args"] == {"youtubepot-bgutilhttp": {"base_url": ["http://192.168.1.10:4416"]}}
    assert "extractor_args" not in YtDlp(tmp_path)._opts()
    monkeypatch.setenv("KIDTUBE_POT_URL", "http://helper:4416")
    assert Config.from_env().pot_url == "http://helper:4416"
