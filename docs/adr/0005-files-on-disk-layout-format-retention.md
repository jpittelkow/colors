# 0005. Files on disk: layout, one playback format, retention

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Downloaded videos need a home on the Unraid array. The TV devices are weak, so the server should never transcode
during playback. Storage is large but not endless.

## Decision

- Layout: `<library>/<Channel name> [<channel id>]/<upload date> - <title> [<video id>].mp4`, with the thumbnail,
  subtitles and an `.info.json` beside each file. Plex and Jellyfin can read this folder too, so the library is usable
  without the app.
- The database is the source of truth for approval, profiles and watch state; the folder is the source of truth for
  what exists. A rescan repairs the database from the sidecar files.
- Every file is stored in one format the TVs play directly: H.264 video, AAC audio, MP4, at most 1080p. yt-dlp asks for
  that format first; anything else is converted once after download. Conversion runs **on the CPU by default**, one
  at a time at low priority. The iGPU (VAAPI) is an opt-in setting limited to set idle hours, because it is shared
  with the other services and a wedged iGPU hung the host on 2026-11-19.
- The server also makes what the app needs to draw a video: a card thumbnail in set sizes and a sprite sheet for
  scrub previews, stored beside the file and served with long cache times.
- A quality cap can be set per subscription (for example 720p for cartoons).
- Subtitles are downloaded when they exist. SponsorBlock segments are stored as data and skipped by the player, not
  cut from the file ([ADR 0024](0024-skip-segments-at-playback.md)).
- Retention rules per subscription: keep everything, keep the last N, or delete watched after X days. "Watched" means
  watched by **every** profile the item is assigned to. Favorites and
  anything in a playlist are never deleted automatically. A total size cap pauses new downloads and alerts.
- A video removed from YouTube stays in the library and is marked "gone from YouTube".

## Consequences

- Playback is plain file serving. No transcoder at watch time.
- H.264 files are bigger than AV1 or VP9 at the same quality.
- CPU conversion is slow. It only applies to the few videos YouTube does not offer in H.264.
- Automatic deletion can remove something a child wanted. The default is "keep everything".

## Alternatives

Keep whatever yt-dlp fetches and transcode on demand: needs a live transcoder and the iGPU at watch time. Store by
video id only: unreadable for people and for Plex.

## Where it lives

`server/app/library/` (`layout.py`, `normalize.py`, `retention.py`, `rescan.py`).
