# 0041. Even out the volume: the server measures, the TV adjusts

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

On YouTube every video plays at about the same loudness, because YouTube turns loud videos down as it plays them.
Downloaded files carry no such adjustment, so in colors one channel is whisper-quiet and the next is loud, and inside
a video a scream or a burst of music jumps out over talking. Jeff asked for both to be evened out.

## Decision

- **Measure once on the server.** A background job ("Volume levels", every 10 minutes) runs ffmpeg's `loudnorm`
  analysis on each downloaded video's sound track: integrated loudness (EBU R128, LUFS) and true peak, stored on
  the item. The file is read, never changed. A file ffmpeg can't read is marked done with no level, so it is not
  tried again.
- **The play answer carries the adjustment**: `"audio": {"gain_db": …, "compress": true}`. The gain brings the
  video to -16 LUFS (a little under YouTube's -14, for a living room), at most +10 dB up and -15 dB down. A video
  not measured yet, or without real sound, gets 0. With the setting off, `"audio"` is null and the TV plays the
  file as it is.
- **The TV applies it** with Android's DynamicsProcessing on the player's audio session: the gain, then one gentle
  compressor band (above -20 dBFS at 2.5:1, soft knee, +2 dB after) for loud moments inside a video, then a limiter
  at -1 dBFS so a quiet video turned up can't clip. If a TV can't give the effect, a too-loud video is still turned
  down with the player's own volume.
- **One switch** on the parents' page (Settings › Household › Even out the volume), on by default, for the whole
  house. It takes effect from the next video.

## Consequences

- Nothing is re-encoded: switching it off is instant and complete, and the originals stay as downloaded.
- The compressor and limiter work on everything the TV app plays, Plex included; the per-video gain only on
  downloaded videos, because only they are measured.
- A Plex movie whose surround track goes to a soundbar undecoded (passthrough) gets no effect at all; Android can
  only process sound it decodes. YouTube downloads are always decoded.
- The first run measures the whole library; each video takes a few seconds of CPU.
- Overall a little quieter than before for loud channels: the TV volume may want a notch up once.

## Alternatives

Re-encoding each file's audio with `loudnorm` at download: simpler on the TV, but permanent, a whole-library
re-encode, and nothing for Plex. Using YouTube's own loudness figure: yt-dlp does not reliably give it, and it
would not cover videos from elsewhere. Android's LoudnessEnhancer: can only turn up.

## Where it lives

`server/app/downloads/loudness.py`, `server/migrations/0007_loudness.sql`, the `loudness` job in
`server/app/background.py`, `audio` in `/api/tv/v1/play`, the switch in `server/app/static/admin/app.js`;
`tv/.../ui/Leveler.kt` and its use in `Player.kt`.
