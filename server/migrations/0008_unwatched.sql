-- Channels nobody watches (ADR 0042): "Keep it" hides a channel from the list until this time.
ALTER TABLE containers ADD COLUMN kept_until REAL;

-- The list asks for each child's newest play per channel.
CREATE INDEX events_item ON events (item_id, profile_id, ts);
