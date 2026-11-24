"""Paths and the port come from the environment; everything else lives in the database (ADR 0003)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    data_dir: Path
    library_dir: Path
    migrations_dir: Path = SERVER_DIR / "migrations"
    run_worker: bool = True
    ffmpeg_dir: str | None = None  # folder holding ffmpeg, when it is not on the PATH
    pot_url: str | None = None  # a PO token helper (bgutil), so YouTube doesn't take us for a bot (ADR 0004)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kidtube.db"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            data_dir=Path(os.environ.get("KIDTUBE_DATA_DIR", "./data")).resolve(),
            library_dir=Path(os.environ.get("KIDTUBE_LIBRARY_DIR", "./library")).resolve(),
            ffmpeg_dir=os.environ.get("KIDTUBE_FFMPEG_DIR") or None,
            pot_url=os.environ.get("KIDTUBE_POT_URL") or None,
        )
