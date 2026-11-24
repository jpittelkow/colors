"""Guard tests: they fail the build when a rule of the design is broken (ADR 0029)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from app import db as db_module
from app.api import tv

APP_DIR = Path(tv.__file__).resolve().parent.parent

# TV routes that return no items and no stream, so they need no pipeline call.
NO_ITEMS = {"pair_start", "pair_status", "profiles"}


def _route_functions(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and getattr(d.func.value, "id", "") == "router"
            for d in node.decorator_list
        ):
            out[node.name] = ast.get_source_segment(source, node)
    return out


def test_every_tv_route_goes_through_the_pipeline():
    """ADR 0022: a TV route that returns items or a stream must get them from the pipeline."""
    routes = _route_functions(APP_DIR / "api" / "tv.py")
    assert routes, "no routes found; the guard is not looking at the right file"
    missing = [name for name, src in routes.items() if name not in NO_ITEMS and "pipeline." not in src]
    assert not missing, f"TV routes that skip the pipeline: {missing}"


def test_tv_responses_never_leak_paths_or_tokens(env):
    """ADR 0017 and ADR 0029: no file path or server secret reaches a TV."""
    sam = env.client.post("/api/admin/profiles", json={"name": "Sam"}).json()["id"]
    tv_client = env.pair()["client"]
    r = env.client.post("/api/admin/add", json={"urls": ["https://example.test/watch?v=abc"], "approve": True})
    item = r.json()["added"][0]
    env.run_jobs()
    bodies = [
        tv_client.get("/api/tv/v1/profiles").json(),
        tv_client.get("/api/tv/v1/home", params={"profile_id": sam}).json(),
        tv_client.post("/api/tv/v1/play", json={"profile_id": sam, "item_id": item}).json(),
    ]
    text = json.dumps(bodies)
    secret = env.db.get_setting("secret_key")
    for banned in ("file_path", "thumb_path", ".mp4", "Trains [chan1]", str(env.cfg.library_dir), secret):
        assert banned not in text, f"a TV response contains {banned!r}"


def test_only_the_downloads_module_imports_yt_dlp():
    """ADR 0004: network access to YouTube stays in one file, so tests can swap it. The updater names yt_dlp too,
    to install a new one and drop the old one from memory, but never calls YouTube."""
    offenders = [
        p.relative_to(APP_DIR).as_posix()
        for p in APP_DIR.rglob("*.py")
        if "yt_dlp" in p.read_text(encoding="utf-8") and p.name not in ("ytdlp.py", "ytdlp_update.py")
    ]
    assert not offenders, offenders


def test_migrations_apply_once_and_back_up_first(tmp_path):
    migrations = tmp_path / "m"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("CREATE TABLE a (x INTEGER);  -- note\n", encoding="utf-8")
    path = tmp_path / "t.db"
    assert db_module.migrate(path, migrations) == ["0001_a.sql"]
    assert db_module.migrate(path, migrations) == []
    (migrations / "0002_b.sql").write_text("CREATE TABLE b (y INTEGER);\nINSERT INTO b VALUES (1);\n", encoding="utf-8")
    assert db_module.migrate(path, migrations) == ["0002_b.sql"]
    assert len(list(tmp_path.glob("t.pre-migrate-*.db"))) == 1


def test_a_broken_migration_changes_nothing(tmp_path):
    import sqlite3

    import pytest

    migrations = tmp_path / "m"
    migrations.mkdir()
    (migrations / "0001_bad.sql").write_text("CREATE TABLE a (x INTEGER);\nNOT SQL;\n", encoding="utf-8")
    path = tmp_path / "t.db"
    with pytest.raises(sqlite3.Error):
        db_module.migrate(path, migrations)
    c = sqlite3.connect(path)
    assert c.execute("SELECT count(*) FROM sqlite_master WHERE name = 'a'").fetchone()[0] == 0
    c.close()
