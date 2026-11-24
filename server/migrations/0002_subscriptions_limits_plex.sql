-- Subscriptions and the inbox (ADR 0004, 0005, 0009), skips (ADR 0024), limits (ADR 0011, 0012), Plex (ADR 0008).

ALTER TABLE containers ADD COLUMN url TEXT NOT NULL DEFAULT '';
ALTER TABLE containers ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE containers ADD COLUMN thumb_path TEXT NOT NULL DEFAULT '';
ALTER TABLE containers ADD COLUMN rested_until TEXT;

ALTER TABLE items ADD COLUMN blocked_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE items ADD COLUMN subtitle_path TEXT NOT NULL DEFAULT '';
ALTER TABLE items ADD COLUMN gone_upstream INTEGER NOT NULL DEFAULT 0;
ALTER TABLE items ADD COLUMN play_note TEXT NOT NULL DEFAULT '';   -- why a Plex item can't play on the TVs
ALTER TABLE items ADD COLUMN media_key TEXT NOT NULL DEFAULT '';   -- Plex part key for streaming

CREATE TABLE subscriptions (
  id           INTEGER PRIMARY KEY,
  container_id INTEGER NOT NULL UNIQUE REFERENCES containers (id) ON DELETE CASCADE,
  url          TEXT NOT NULL,
  mode         TEXT NOT NULL DEFAULT 'new' CHECK (mode IN ('new', 'all', 'last')),
  last_n       INTEGER NOT NULL DEFAULT 10,
  min_s        INTEGER NOT NULL DEFAULT 0,
  max_s        INTEGER NOT NULL DEFAULT 0,       -- 0 = no maximum
  skip_shorts  INTEGER NOT NULL DEFAULT 1,
  skip_live    INTEGER NOT NULL DEFAULT 1,
  title_must   TEXT NOT NULL DEFAULT '',          -- comma separated, any must match
  title_not    TEXT NOT NULL DEFAULT '',          -- comma separated, none may match
  check_hours  INTEGER NOT NULL DEFAULT 6,
  daily_cap    INTEGER NOT NULL DEFAULT 10,
  keep_mode    TEXT NOT NULL DEFAULT 'all' CHECK (keep_mode IN ('all', 'last', 'watched')),
  keep_n       INTEGER NOT NULL DEFAULT 30,
  keep_days    INTEGER NOT NULL DEFAULT 60,
  active       INTEGER NOT NULL DEFAULT 1,
  last_checked REAL,
  last_error   TEXT NOT NULL DEFAULT '',
  created_at   REAL NOT NULL
);

-- Every video id a subscription has seen, so "new uploads only" can tell old from new.
CREATE TABLE sub_seen (
  sub_id      INTEGER NOT NULL REFERENCES subscriptions (id) ON DELETE CASCADE,
  external_id TEXT NOT NULL,
  PRIMARY KEY (sub_id, external_id)
);

CREATE TABLE segments (
  id       INTEGER PRIMARY KEY,
  item_id  INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
  start_s  REAL NOT NULL,
  end_s    REAL NOT NULL,
  category TEXT NOT NULL,
  origin   TEXT NOT NULL DEFAULT 'sponsorblock' CHECK (origin IN ('sponsorblock', 'parent'))
);
CREATE INDEX segments_item ON segments (item_id);

CREATE TABLE limits (
  profile_id    INTEGER PRIMARY KEY REFERENCES profiles (id) ON DELETE CASCADE,
  weekday_min   INTEGER,              -- NULL = no daily limit
  weekend_min   INTEGER,
  session_min   INTEGER,              -- NULL = no session limit
  break_min     INTEGER NOT NULL DEFAULT 60,
  closed_from   TEXT,                 -- 'HH:MM', NULL = never closed
  closed_to     TEXT,
  timefit       INTEGER NOT NULL DEFAULT 1,
  grace_min     INTEGER NOT NULL DEFAULT 2,
  show_timer    INTEGER NOT NULL DEFAULT 1,
  autoplay_n    INTEGER NOT NULL DEFAULT 2
);

-- Seconds of watched time per profile per day ('YYYY-MM-DD' after the rollover hour).
CREATE TABLE watch_time (
  profile_id INTEGER NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
  day        TEXT NOT NULL,
  seconds    REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (profile_id, day)
);

-- Parent actions that change today's time: extra minutes, one-off limits, "last one", end now.
CREATE TABLE overrides (
  id         INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('extra', 'oneoff', 'lastone', 'lock', 'unlock')),
  day        TEXT NOT NULL,
  minutes    REAL NOT NULL DEFAULT 0,
  starts_at  REAL NOT NULL,
  ends_at    REAL,
  note       TEXT NOT NULL DEFAULT '',
  done       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX overrides_profile ON overrides (profile_id, day);

-- Sessions: a run of watching with no gap longer than the session break.
CREATE TABLE sessions (
  profile_id INTEGER PRIMARY KEY REFERENCES profiles (id) ON DELETE CASCADE,
  started_at REAL NOT NULL,
  last_at    REAL NOT NULL,
  seconds    REAL NOT NULL DEFAULT 0
);

-- What a device is playing right now, for "now playing" and for counting time.
ALTER TABLE devices ADD COLUMN last_profile_id INTEGER;
ALTER TABLE devices ADD COLUMN last_position_s REAL NOT NULL DEFAULT 0;
ALTER TABLE devices ADD COLUMN last_state TEXT NOT NULL DEFAULT '';
ALTER TABLE devices ADD COLUMN fit_left_s REAL;          -- time left when the current video started
