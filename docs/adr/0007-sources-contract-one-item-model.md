# 0007. Sources contract: one item model for every kind of content

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The app should be all-in-one: downloaded YouTube videos, Plex and Jellyfin shows and movies, live kids' channels,
music, and later home videos. The TV app must not care where a video comes from.

## Decision

- Each origin is a **source** that implements one contract: list containers, list items, give details, give a playable
  stream, report and accept watch state.
- Every source maps its content onto the same model:
  - **Container**: a YouTube channel, a show, a movie collection, a live channel group, a music playlist.
  - **Item**: one playable thing with title, artwork, length in seconds, and kind (video, episode, movie, live, audio).
- To a child, a show looks like a channel and an episode looks like a video.
- Planned sources, in order: local library, Plex, Jellyfin, live TV from the Dispatcharr Kids profile, music through
  Music Assistant, a family folder of home videos and video messages.
- Approval, profile assignment, tags, rows, playlists and time rules attach to containers and items, never to a source.
  Every rule therefore works on every source.
- An item with no known length (live TV) is handled by the time rules as a special case
  ([ADR 0012](0012-only-show-what-finishes-in-time.md)).

## Consequences

- One set of curation and limit code for everything.
- The model is the lowest common denominator. Source-specific extras (seasons, YouTube playlists) are flattened or
  carried as optional fields.
- Each new source is real work: mapping, artwork, stream handling, watch-state sync.

## Alternatives

Copy Plex and Jellyfin files into the local library: doubles storage and breaks their watch state. Separate sections
per source in the app: not the all-in-one feel the owner asked for.

## Where it lives

`server/app/sources/` (`base.py`, `local.py`, `plex.py`, `jellyfin.py`, `live.py`, `music.py`, `family.py`).
