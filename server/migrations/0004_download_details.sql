-- Downloads page (ADR 0032, revised): a parent can stop a download, and the history shows how big it was.

ALTER TABLE jobs ADD COLUMN stopped INTEGER NOT NULL DEFAULT 0;   -- 1: stopped by a parent, not a failure
ALTER TABLE jobs ADD COLUMN bytes INTEGER NOT NULL DEFAULT 0;     -- size of the finished file
ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;  -- how many times it has been tried
