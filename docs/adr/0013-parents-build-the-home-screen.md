# 0013. Parents build the home screen; recommendations are rules

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

YouTube's recommendations are the thing being replaced. The boys should still get a home screen that feels alive, with
rows, "up next" and new things to find.

## Decision

- The home screen for each profile is a list of **rows** a parent orders. A row is one of:
  - a hand-picked list or playlist;
  - a saved filter (tag, container, source, kind, length, newest, not yet watched);
  - a built-in: Continue watching, New this week, Favorites, Watch it again.
- **Categories** across the top (Shows, Music, Learning, Explore) are saved filters over tags, to match the YouTube
  Kids layout ([ADR 0016](0016-match-the-youtube-kids-look.md)).
- Rows can have a **date range or weekly times**: seasonal rows, "Saturday morning cartoons".
- Items can be **pinned** to the top of a row with an expiry date.
- A container can be **rested**: hidden for a set number of weeks, then back.
- **Recommendations are rules a parent can read**, not a learned model. "Up next" picks from the same container, then
  the same tag, then the same row, preferring unwatched. Parents can add rules such as "after two cartoons, offer a
  learning video".
- **Autoplay** is per profile: off, or a chain of at most N videos, then back to the home screen.
- **Playlists**: per child or shared. A playlist can end with a stop (bedtime wind-down).
- **A looping channel**: a playlist can be presented as a live-style channel that plays a schedule, for a TV feel.
- Everything on the home screen has already passed the visibility pipeline
  ([ADR 0022](0022-one-visibility-pipeline-for-rules.md)).
- The server sends the finished home screen to the app. The app draws it and decides nothing
  ([ADR 0017](0017-the-tv-app-is-a-thin-client.md)).

## Consequences

- Parents can say why any video was shown.
- Setting up rows is work. Defaults (the built-in rows plus one row per tag) give a usable screen with no setup.
- No clever discovery. AI can suggest rows and channels to the parent ([ADR 0014](0014-ai-is-optional-and-only-advises.md)),
  but it never changes the screen itself.

## Alternatives

A learned recommender on watch history: opaque, and it optimises for watch time. A single flat grid: no feel of
YouTube, and hard to browse.

## Where it lives

`server/app/curation/` (`rows.py`, `upnext.py`, `playlists.py`, `channel_loop.py`), `server/app/api/home.py`.
