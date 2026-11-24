-- A failed download tries again by itself after a short wait (ADR 0032, revised).

ALTER TABLE jobs ADD COLUMN retry_at REAL;   -- a queued job waits until this time; NULL = ready now
