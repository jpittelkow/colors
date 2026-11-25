-- How loud each downloaded video is, measured once with ffmpeg (EBU R128), so the TV can even out the volume
-- (ADR 0041).

ALTER TABLE items ADD COLUMN loudness_lufs REAL;   -- integrated loudness; NULL = not measured or no sound found
ALTER TABLE items ADD COLUMN loudness_peak REAL;   -- true peak, dBTP
ALTER TABLE items ADD COLUMN loudness_at REAL;     -- when it was measured (or tried); NULL = still to do
