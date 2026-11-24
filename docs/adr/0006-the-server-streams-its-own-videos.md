# 0006. The server streams its own videos

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Downloaded videos could be streamed by Plex or Jellyfin, with this project only adding curation. Or the server could
serve the files itself.

## Decision

The server serves its own downloaded files over HTTP with range requests. The TV app plays them directly. Because every
file is already in one playable format ([ADR 0005](0005-files-on-disk-layout-format-retention.md)), there is no
transcoding. Each stream URL carries a signed token tied to the device, the profile and the item. It is valid for the
item's length plus a margin and is extended by the playback heartbeat
([ADR 0011](0011-the-server-keeps-the-clock.md)), so a long video never loses its stream mid-way, and a URL copied out
of the app stops working once playback ends.

Plex and Jellyfin content is different: it is streamed from those servers
([ADR 0008](0008-plex-and-jellyfin-allow-listed-streamed-in-place.md)).

## Consequences

- Approval, profiles, time limits and streaming live in one place. A child cannot reach a downloaded video except
  through a check.
- The downloaded library does not depend on Plex or Jellyfin being up.
- We own seeking, scrub thumbnails and subtitles ourselves.

## Alternatives

Let Plex stream everything: Plex would need a library per child, its own app remains a way around the limits, and time
rules would live in two places.

## Where it lives

`server/app/api/stream.py`.
