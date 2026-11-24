-- Channel pictures (ADR 0030), named jobs (ADR 0032), AI (ADR 0034), import (ADR 0035), avatars (ADR 0036).

-- One row per YouTube channel id we have looked up a picture for. file is relative to data_dir.
CREATE TABLE channel_cache (
  channel_id TEXT PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '',
  avatar_url TEXT NOT NULL DEFAULT '',
  file       TEXT NOT NULL DEFAULT '',
  fetched_at REAL NOT NULL,
  error      TEXT NOT NULL DEFAULT ''
);

-- Each run of a named background job. Trimmed to the last 200 per job.
CREATE TABLE job_runs (
  id          INTEGER PRIMARY KEY,
  job         TEXT NOT NULL,
  started_at  REAL NOT NULL,
  finished_at REAL,
  state       TEXT NOT NULL DEFAULT 'running' CHECK (state IN ('running', 'done', 'failed', 'stopped')),
  result      TEXT NOT NULL DEFAULT '',
  error       TEXT NOT NULL DEFAULT '',
  by_hand     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX job_runs_job ON job_runs (job, id);

-- Every OpenRouter call: what it was for, tokens and price, for the monthly cap.
CREATE TABLE ai_calls (
  id         INTEGER PRIMARY KEY,
  ts         REAL NOT NULL,
  purpose    TEXT NOT NULL,
  model      TEXT NOT NULL,
  tokens_in  INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  cost_usd   REAL NOT NULL DEFAULT 0,
  ok         INTEGER NOT NULL DEFAULT 1,
  error      TEXT NOT NULL DEFAULT ''
);

-- Channels and videos the AI suggested to the parents, already checked against YouTube.
CREATE TABLE suggestions (
  id         INTEGER PRIMARY KEY,
  kind       TEXT NOT NULL CHECK (kind IN ('channel', 'video')),
  external_id TEXT NOT NULL,
  url        TEXT NOT NULL,
  title      TEXT NOT NULL,
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url  TEXT NOT NULL DEFAULT '',
  duration_s REAL NOT NULL DEFAULT 0,
  reason     TEXT NOT NULL DEFAULT '',
  for_profiles TEXT NOT NULL DEFAULT '',       -- comma separated profile ids
  status     TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'added', 'dismissed')),
  created_at REAL NOT NULL,
  UNIQUE (kind, external_id)
);

-- The cached "Picked for you" order per profile: item ids only, filtered again when drawn.
CREATE TABLE picks (
  profile_id INTEGER PRIMARY KEY REFERENCES profiles (id) ON DELETE CASCADE,
  item_ids   TEXT NOT NULL DEFAULT '[]',
  built_at   REAL NOT NULL,
  by_ai      INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE profiles ADD COLUMN avatar_color TEXT NOT NULL DEFAULT '';
ALTER TABLE profiles ADD COLUMN picks_on INTEGER NOT NULL DEFAULT 1;

-- An import: the links a parent gave, read one at a time, then reviewed and applied.
CREATE TABLE imports (
  id         INTEGER PRIMARY KEY,
  source     TEXT NOT NULL,                 -- 'paste' | 'takeout' | 'playlist'
  state      TEXT NOT NULL DEFAULT 'reading' CHECK (state IN ('reading', 'review', 'applying', 'done', 'failed')),
  created_at REAL NOT NULL,
  error      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE import_rows (
  id          INTEGER PRIMARY KEY,
  import_id   INTEGER NOT NULL REFERENCES imports (id) ON DELETE CASCADE,
  url         TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT '',      -- 'channel' | 'video' once read
  state       TEXT NOT NULL DEFAULT 'waiting' CHECK (state IN ('waiting', 'read', 'failed', 'done', 'skipped')),
  external_id TEXT NOT NULL DEFAULT '',
  title       TEXT NOT NULL DEFAULT '',
  channel_id  TEXT NOT NULL DEFAULT '',
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url   TEXT NOT NULL DEFAULT '',
  duration_s  REAL NOT NULL DEFAULT 0,
  video_count INTEGER NOT NULL DEFAULT 0,
  in_library  INTEGER NOT NULL DEFAULT 0,
  error       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX import_rows_import ON import_rows (import_id, id);
