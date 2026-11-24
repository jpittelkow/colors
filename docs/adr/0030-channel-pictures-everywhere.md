# 0030. Channel pictures everywhere, fetched once and cached

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The design system says pictures carry the colour (README, "Keep it calm"). Search results show only letters for
channels, because yt-dlp's fast search returns video thumbnails but no channel pictures. Getting a channel's
picture takes one extra request per channel.

## Decision

- A `channel_cache` table keeps, per YouTube channel id: name, picture URL, a local copy of the picture, and when it
  was fetched. Entries are refreshed after 30 days.
- Search answers at once with what it has: cached pictures where known, letters where not. The server then looks up
  the missing channels in the background, at most 8 per search and 2 at a time, and the page swaps each letter for
  the picture when it arrives (the page asks again for those channels a few seconds later).
- Channel pictures are served from our own copy (`/api/admin/channel-pictures/<id>`), so the page doesn't load
  Google's servers for every row, and pictures survive a channel changing its URL.
- The same cache fills pictures for channels in the library, subscriptions and video screens, so every place a
  channel appears shows its picture.
- The lookup goes through the downloader object, like all YouTube traffic (ADR 0004), so tests use a fake.

## Consequences

- Search stays fast; pictures fill in a second or two later.
- More requests to YouTube: one per new channel, then none for 30 days.
- A few more megabytes in app data for the picture copies.

## Alternatives

Fetch every channel before answering: search would take many seconds. YouTube Data API: needs a key and quota.
Leave letters: fails the design system's main rule.

## Where it lives

`server/migrations/0003_*.sql` (`channel_cache`), `server/app/downloads/channels.py`, `server/app/api/admin.py`
(search), `server/app/static/admin/app.js`.
