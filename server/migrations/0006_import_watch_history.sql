-- Import from a Takeout watch history (ADR 0035, revised): how often a video was watched, and whose file it came from.

ALTER TABLE imports ADD COLUMN note TEXT NOT NULL DEFAULT '';             -- one line for the parent, shown in review
ALTER TABLE import_rows ADD COLUMN watches INTEGER NOT NULL DEFAULT 0;    -- times watched; a channel row holds the sum
ALTER TABLE import_rows ADD COLUMN profile_ids TEXT NOT NULL DEFAULT '';  -- '3,4': who it is for by default; '' = all
