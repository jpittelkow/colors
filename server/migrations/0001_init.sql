-- Milestone 1 schema. See docs/adr/0007 (item model), 0009 (approval), 0010 (profiles), 0021 (events).

CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE profiles (
  id       INTEGER PRIMARY KEY,
  name     TEXT NOT NULL,
  kind     TEXT NOT NULL DEFAULT 'child' CHECK (kind IN ('child', 'guest', 'grownup')),
  avatar   TEXT NOT NULL DEFAULT '',
  birthday TEXT,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE containers (
  id          INTEGER PRIMARY KEY,
  source      TEXT NOT NULL DEFAULT 'local',
  kind        TEXT NOT NULL DEFAULT 'channel',
  external_id TEXT NOT NULL,
  title       TEXT NOT NULL,
  thumb_url   TEXT NOT NULL DEFAULT '',
  trusted     INTEGER NOT NULL DEFAULT 0,
  added_at    REAL NOT NULL,
  UNIQUE (source, external_id)
);

CREATE TABLE items (
  id           INTEGER PRIMARY KEY,
  container_id INTEGER NOT NULL REFERENCES containers (id) ON DELETE CASCADE,
  source       TEXT NOT NULL DEFAULT 'local',
  external_id  TEXT NOT NULL,
  url          TEXT NOT NULL DEFAULT '',
  kind         TEXT NOT NULL DEFAULT 'video',
  title        TEXT NOT NULL,
  description  TEXT NOT NULL DEFAULT '',
  duration_s   REAL NOT NULL DEFAULT 0,
  upload_date  TEXT NOT NULL DEFAULT '',
  thumb_url    TEXT NOT NULL DEFAULT '',
  file_path    TEXT NOT NULL DEFAULT '',   -- relative to the library folder; never sent to a TV
  thumb_path   TEXT NOT NULL DEFAULT '',
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ready', 'failed')),
  approval     TEXT NOT NULL DEFAULT 'waiting' CHECK (approval IN ('waiting', 'approved', 'hidden')),
  added_at     REAL NOT NULL,
  UNIQUE (source, external_id)
);
CREATE INDEX items_container ON items (container_id);
CREATE INDEX items_visible ON items (approval, status);

-- A row assigns either a whole container or one item to a profile.
CREATE TABLE assignments (
  profile_id   INTEGER NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
  container_id INTEGER REFERENCES containers (id) ON DELETE CASCADE,
  item_id      INTEGER REFERENCES items (id) ON DELETE CASCADE,
  CHECK ((container_id IS NULL) <> (item_id IS NULL))
);
CREATE UNIQUE INDEX assignments_container ON assignments (profile_id, container_id) WHERE container_id IS NOT NULL;
CREATE UNIQUE INDEX assignments_item ON assignments (profile_id, item_id) WHERE item_id IS NOT NULL;

CREATE TABLE tags (
  target_type TEXT NOT NULL CHECK (target_type IN ('item', 'container')),
  target_id   INTEGER NOT NULL,
  tag         TEXT NOT NULL,
  by_ai       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (target_type, target_id, tag)
);

CREATE TABLE jobs (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL DEFAULT 'download',
  item_id     INTEGER REFERENCES items (id) ON DELETE CASCADE,
  state       TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed')),
  progress    REAL NOT NULL DEFAULT 0,
  error       TEXT NOT NULL DEFAULT '',
  created_at  REAL NOT NULL,
  started_at  REAL,
  finished_at REAL
);
CREATE INDEX jobs_state ON jobs (state, id);

CREATE TABLE devices (
  id             INTEGER PRIMARY KEY,
  name           TEXT NOT NULL DEFAULT '',
  token_hash     TEXT NOT NULL UNIQUE,
  pair_code      TEXT,
  paired_at      REAL,
  revoked        INTEGER NOT NULL DEFAULT 0,
  created_at     REAL NOT NULL,
  last_seen      REAL,
  last_item_id   INTEGER,
  last_heartbeat REAL
);

CREATE TABLE watch_state (
  profile_id INTEGER NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
  item_id    INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  position_s REAL NOT NULL DEFAULT 0,
  watched    INTEGER NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL,
  PRIMARY KEY (profile_id, item_id)
);

CREATE TABLE events (
  id         INTEGER PRIMARY KEY,
  ts         REAL NOT NULL,
  profile_id INTEGER,
  device_id  INTEGER,
  item_id    INTEGER,
  type       TEXT NOT NULL,
  data       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX events_profile ON events (profile_id, ts);
