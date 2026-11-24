# 0024. Skip sponsor and filler segments at playback, not by cutting files

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Kids' YouTube videos carry sponsor reads, "like and subscribe" asks, and long intros and outros. SponsorBlock has
community-marked segments for many videos. Cutting them out of the file is permanent and the marks are sometimes wrong.

## Decision

- At download, the server fetches SponsorBlock segments for the video and stores them as data: start, end, category.
- A parent chooses which categories to skip, globally and per container (sponsor, self-promotion, interaction
  reminder, intro, outro).
- The play answer ([ADR 0017](0017-the-tv-app-is-a-thin-client.md)) includes the segments to skip. The player jumps
  over them without a button.
- A parent can add, edit or remove segments by hand in the admin page, including a trimmed start or end for a video.
- The same mechanism carries **parts** of long items ([ADR 0028](0028-long-items-parts-and-movie-night.md)): a part
  is a start and an end.
- An item's length for all time rules is its length **after** skips.
- Segments are refreshed once, a few weeks after download, since marks arrive late.

## Consequences

- Files stay untouched; a wrong mark is fixed by editing data.
- Skips only work in our app. The same file in Plex plays in full.
- SponsorBlock is an outside service queried by video id. If it is down, the video still downloads without segments.

## Alternatives

Cut at download with yt-dlp's SponsorBlock removal: saves a little disk, loses the original, and bakes in mistakes.
No skipping: the ads-in-content stay.

## Where it lives

`server/app/library/segments.py`, `tv/` (`player/SegmentSkipper.kt`).
