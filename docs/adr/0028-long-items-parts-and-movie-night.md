# 0028. Long items: parts and the movie-night pass

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

With time-fit ([ADR 0012](0012-only-show-what-finishes-in-time.md)), a movie or a 45-minute video would almost never
be shown under a normal limit. Split out of ADR 0012 after the audit so it can change on its own.

## Decision

- **Parts.** A long item can be split into parts at chapter marks, or at a set length when it has no chapters. A part
  is a start and an end offset on the same file or stream, stored with the skip segments
  ([ADR 0024](0024-skip-segments-at-playback.md)). No new files are made.
- Each part is an item for time-fit. Finishing a part marks it watched and offers the next one, today if it fits or
  as "continue" next time.
- Splitting is a choice per item or per container, off by default. The admin page suggests it for items longer than a
  set length.
- **Movie-night pass.** A parent can grant one named item that ignores time-fit once, for one profile or for together
  mode. The pass expires at the end of the day if unused. Watched time is still counted and can take the allowance
  below zero for that day only.

## Consequences

- Movies and long videos stay usable under limits.
- A part that ends mid-scene is still an abrupt stop. Chapter marks help; set-length splits do not.
- Plex and Jellyfin watch state is per whole item, so parts sync back as progress, not as watched.

## Alternatives

Never show long items under a limit: movies vanish on normal days. Cut files into parts: doubles storage and breaks
Plex.

## Where it lives

`server/app/limits/parts.py`, `server/app/limits/passes.py`.
