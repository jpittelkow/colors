# 0042. Channels nobody watches: a list that suggests, per child

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

Channels pile up. A subscription keeps downloading every day whether anyone watches it or not: disk space, download
time, and a more crowded home screen for children who can't read. A boy outgrows a channel and nobody notices, because
nothing tells a parent that something is *not* happening. Jeff asked for a way to see which channels haven't been
watched at all in a long time.

The server already has what's needed. Every play is logged as a `started` event with the profile and the item
([ADR 0021](0021-watch-history-stays-home.md)), and every item belongs to a container. A channel's last play, per
child, is the newest such event. No new tracking is needed and nothing leaves the house.

## Decision

- **Not watched** means no play *started* by that child on any item of the channel for **30 days**. The threshold is a
  household setting (Settings › Household). His last play is the newest `started` or `finished` event, or resume
  point, on any of the channel's videos. Only starts count for now, because skips and progress are not logged yet
  (ADR 0021). Once they are, a play the child left within the skip share stops counting.
- **Per child, one list.** One card per channel, showing each child it is assigned to and when he last watched it
  ("never" if he hasn't). A card is listed if any of its children hasn't watched it within the threshold, so a
  channel one boy outgrew while the other still loves it shows up with that split visible ("Still watching").
- **Only channels the child could reach:** assigned to him (the whole channel or any of its videos), not resting
  (`rested_until`), with at least one ready, approved video. Left out:
  - a channel that came into colors less than the threshold ago (new, not unloved). For a child who never played it,
    the clock starts when the channel was added;
  - a channel with no playable videos. Those go in their own small "Nothing to play" list, because the fix is about
    downloads or approval.
- **The likely reason, when the server can tell**, as a "Why, maybe" note under that child:
  - he has finished every video in it (nothing new to watch);
  - every video is longer than his daily limit, with time-fit on
    ([ADR 0012](0012-only-show-what-finishes-in-time.md)), so none can ever be offered.
  A "not on his home screen" reason was considered and dropped: the TV already gives every channel he can reach its
  own home-screen row, so it can't happen. Otherwise the card gives no reason.
- **It suggests; it never acts** ([ADR 0014](0014-ai-is-optional-and-only-advises.md) in spirit). Each card offers:
  - **Pause downloads**, first, when the channel has an active subscription. Its videos and rules stay. The card says
    how many videos came in since anyone last watched;
  - **Take away from (name)**, when another child still watches it, instead of deleting it for both;
  - **Rest 30 days**;
  - **Delete**, showing the disk space it frees, with a second tap to confirm. For a Plex show, **Stop allowing**
    (Plex keeps the files);
  - **Keep it**, which hides the card for 90 days.
  Everything except Delete has an Undo. Downloads are never paused on their own.
- **Pausing is a real subscription state.** `PATCH /subscriptions/{id}` pauses or resumes. The subscription settings
  get a "Download new videos" switch (saving them no longer switches a paused subscription back on), and the channel
  page shows "Downloads paused" with a Resume button.
- **Where:** the parents' page Library gets a third view, "Not watched lately", next to Channels and Videos, with its
  count on the button. The Everyone / per-child chips filter it. When the weekly digest is built, it gets one line
  ("4 channels haven't been watched in 30 days").
- **Imported history** ([ADR 0035](0035-importing-what-is-already-approved.md)) does not count: the import keeps no
  dated plays. For an imported channel, the clock starts when it was added to colors.
- **Plex and Jellyfin shows** follow the same rules as YouTube channels.
- **The yearly reduction** of raw events to daily totals (ADR 0021, not built yet) must keep a last-played date per
  child and container, or this list would forget everything older than a year.

## Consequences

- Parents see what's dead weight and can free disk space and home-screen room with one tap per channel.
- One new column, `containers.kept_until`, an index on `events (item_id, profile_id, ts)`, and one setting
  (`unwatched_days`). The list is computed when the Library opens; disk sizes are read only for the listed channels.
- Counting a 5-second start as watched under-reports neglect until skips are logged.
- "Never" for an imported channel is anchored on its add date, not on when the boys last watched it on YouTube.

## Alternatives

- **Household only** (watched by either child counts): simpler, but hides a channel one boy has outgrown.
- **Auto-pause downloads after 60 days**: saves disk space without a tap, but changes what the children have without a
  parent deciding. Rejected; the list suggests pausing instead.
- **Sort channels by last watched, no list**: no reasons, no per-child split, nothing tells a parent to look.

## Where it lives

`server/app/curation/unwatched.py` (the report, Keep it), `server/app/api/manage.py` (`GET /unwatched`,
`POST`/`DELETE /unwatched/{id}/keep`, `PATCH /subscriptions/{id}`, the `unwatched_days` setting),
`server/migrations/0008_unwatched.sql`, `server/app/static/admin/app.js` (Library › Not watched lately, the
subscription switch, the channel page's paused tag), `server/tests/test_unwatched.py`. Related: ADR 0012, 0014, 0021,
0035.
