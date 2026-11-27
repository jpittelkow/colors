-- ADR 0044: autoplay shows the screen between videos (1) or goes straight on to the next one (0, "fast").
ALTER TABLE limits ADD COLUMN autoplay_screen INTEGER NOT NULL DEFAULT 1;
