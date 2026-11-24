"""Updating yt-dlp without rebuilding the image (2026-11-24, after the stash downloader's self-update).

YouTube changes often and yt-dlp follows within days, so waiting for an image rebuild leaves downloads broken. A
parent (or the daily check, when allowed) installs the newest yt-dlp into <data>/pylib:

- The data folder because the server runs as an unprivileged user that can't write the image's site-packages, and
  because it survives a redeploy.
- Only yt-dlp and the exact yt-dlp-ejs it pins (`--no-deps`): its other helpers are already in the image, and a
  second copy of requests or websockets ahead of the image's would shadow what the server itself uses.
- Into a side folder first, swapped in only when pip succeeded.
- Then loaded in place: yt-dlp is only ever imported inside the downloader's methods, so dropping it from
  sys.modules makes the next call import the new one. No restart; a download already running finishes on the old.
- At startup the copy in <data>/pylib is used only when it is newer than the image's, so a newer image wins.
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION_RE = re.compile(r"""__version__\s*=\s*['"]([^'"]+)['"]""")
EJS_RE = re.compile(r"^yt-dlp-ejs\s*==\s*([\w.]+)")
PYPI = "https://pypi.org/pypi/yt-dlp/json"
_dir: Path | None = None


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", version or ""))


def _version_in(folder: Path) -> str | None:
    f = folder / "yt_dlp" / "version.py"
    if not f.is_file():
        return None
    m = VERSION_RE.search(f.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def image_version() -> str | None:
    """The yt-dlp that came with the image (the first copy on the path that isn't ours)."""
    for p in sys.path:
        if not p or (_dir and Path(p) == _dir):
            continue
        v = _version_in(Path(p))
        if v:
            return v
    return None


def loaded_version() -> str:
    from yt_dlp.version import __version__

    return __version__


def _put_first() -> None:
    p = str(_dir)
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)


def activate(data_dir: Path) -> str | None:
    """At startup: put <data>/pylib first on the path when its yt-dlp is newer than the image's. Returns its version,
    or None when the image's is used."""
    global _dir
    _dir = data_dir / "pylib"
    mine, image = _version_in(_dir), image_version()
    if mine and (not image or _key(mine) > _key(image)):
        _put_first()
        return mine
    return None


def newest() -> tuple[str, str | None]:
    """The newest yt-dlp on PyPI and the yt-dlp-ejs version it pins."""
    with urllib.request.urlopen(PYPI, timeout=15) as r:
        info = json.loads(r.read().decode("utf-8"))["info"]
    ejs = next((m.group(1) for d in info.get("requires_dist") or [] if (m := EJS_RE.match(d))), None)
    return info["version"], ejs


def _pip(target: Path, packages: list[str]) -> None:
    p = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-deps", "--disable-pip-version-check",
         "--target", str(target), *packages],
        capture_output=True, text=True, timeout=900)
    if p.returncode:
        raise RuntimeError(f"pip failed: {(p.stderr or p.stdout).strip()[-400:]}")


def _reload() -> None:
    """Forget the loaded yt-dlp so the next import takes the one now first on the path."""
    _put_first()
    for name in list(sys.modules):
        if name == "yt_dlp" or name.startswith(("yt_dlp.", "yt_dlp_ejs", "yt_dlp_plugins")):
            del sys.modules[name]
    importlib.invalidate_caches()
    import yt_dlp  # noqa: F401  (loads it now, so a broken install shows here and not in the next download)


def update(data_dir: Path) -> dict:
    """Install the newest yt-dlp into <data>/pylib and load it. {"updated": bool, "from": old, "version": now}."""
    global _dir
    _dir = data_dir / "pylib"
    have = loaded_version()
    new, ejs = newest()
    if _key(new) <= _key(have):
        return {"updated": False, "from": have, "version": have}
    fresh, old = _dir.with_name("pylib.new"), _dir.with_name("pylib.old")
    shutil.rmtree(fresh, ignore_errors=True)
    _pip(fresh, [f"yt-dlp=={new}"] + ([f"yt-dlp-ejs=={ejs}"] if ejs else []))
    if _version_in(fresh) != new:
        raise RuntimeError(f"pip finished but yt-dlp {new} is not in {fresh}")
    shutil.rmtree(old, ignore_errors=True)
    if _dir.exists():
        _dir.rename(old)
    fresh.rename(_dir)
    shutil.rmtree(old, ignore_errors=True)
    _reload()
    return {"updated": True, "from": have, "version": loaded_version()}
