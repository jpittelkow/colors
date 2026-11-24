# 0004. Download with yt-dlp: a queue, a schedule and rules per channel

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Content comes from YouTube as single videos, playlists and channels. YouTube changes often, downloads fail, and a
channel can have thousands of uploads we do not want.

## Decision

- yt-dlp is used as a Python library, pinned in the image and updatable from the admin page without a rebuild.
- **Search** uses yt-dlp's own search (no YouTube API key). **Add by URL** accepts any video, playlist, channel or
  Short and works out which it is.
- A **subscription** has rules: all uploads, new uploads only, last N, title must or must not match, skip Shorts, skip
  live streams, minimum and maximum length, quality cap.
- Every download is a row in a `jobs` table: queued, running, done, failed, with progress, log and retry. One download
  at a time by default, with a delay between them; both are settings.
- A scheduler checks each subscription on its own interval.
- A first import of a big channel is paced: a daily cap on downloads per subscription and a pause when YouTube starts
  answering with bot checks, so the home address is not throttled.
- A cookies file is supported, from a **throwaway Google account only**, never a family account: an account used this
  way can be flagged. When several downloads in a row fail with the same error, the server raises an alert
  ([ADR 0023](0023-one-docker-container-and-alerts.md)) instead of retrying forever.
- A video already in the library is never downloaded twice (keyed on the YouTube video id).
- Downloading a video does **not** make it visible to a child. Approval is separate
  ([ADR 0009](0009-nothing-is-shown-unless-approved.md)).
- Ways in besides the admin page: a phone share target and a browser bookmarklet, both calling the same "add by URL"
  endpoint, and one-off imports (a YouTube account's history or likes export, starter packs).

## Consequences

- No API key or Google account is needed to search and download.
- yt-dlp will break from time to time. The update button and the alert are how we live with that.
- Downloading breaks YouTube's terms of service. This is a private, home-only library
  ([ADR 0002](0002-scope-home-only-android-tv-first.md)).
- Sequential downloads are slow for a big first import.

## Alternatives

YouTube Data API for search: needs a key and quota, and still needs yt-dlp to download. Streaming through yt-dlp
without saving: fragile, needs internet, and videos vanish when YouTube removes them.

## Where it lives

`server/app/downloads/` (`search.py`, `jobs.py`, `subscriptions.py`, `scheduler.py`, `ytdlp_update.py`).
