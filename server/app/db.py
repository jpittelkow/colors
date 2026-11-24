"""SQLite access and numbered migrations (ADR 0003, ADR 0029)."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

KEEP_BACKUPS = 5


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            with c:  # one transaction per use
                yield c
        finally:
            c.close()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _backup(path: Path) -> None:
    """Online backup before a migration, keeping the last few."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.stem}.pre-migrate-{stamp}.db")
    src = sqlite3.connect(path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    old = sorted(path.parent.glob(f"{path.stem}.pre-migrate-*.db"))
    for f in old[:-KEEP_BACKUPS]:
        f.unlink(missing_ok=True)


def migrate(path: Path, migrations_dir: Path) -> list[str]:
    """Apply pending migrations in order. Returns the names applied."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    c = sqlite3.connect(path)
    try:
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at REAL NOT NULL)")
        c.commit()
        done = {r[0] for r in c.execute("SELECT name FROM schema_migrations")}
        pending = [f for f in sorted(migrations_dir.glob("*.sql")) if f.name not in done]
        if pending and existed and done:
            _backup(path)
        for f in pending:
            sql = f.read_text(encoding="utf-8")
            try:
                c.execute("BEGIN")
                for statement in _split(sql):
                    c.execute(statement)
                c.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", (f.name, time.time()))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return [f.name for f in pending]
    finally:
        c.close()


def _split(sql: str) -> list[str]:
    """Split a migration file into statements. Migrations do not use triggers, so ';' at a line end is enough."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    out, buf = [], []
    for ln in lines:
        code = ln.split("--", 1)[0].rstrip()
        if not code:
            continue
        buf.append(code)
        if code.endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
