# 0012. Only show what will finish in the time left

- **Status:** Accepted
- **Date:** 2026-11-22 (revised the same day after the audit; long items moved to ADR 0028)

## Context

Ending a video halfway causes the fight. The owner's idea: when a time limit is set, the app shows only videos that will
finish inside it, so the limit ends at the end of a video.

## Decision

- **The rule.** An item is shown when `length left to watch <= time left + grace`.
  - *Time left* is the tightest limit from [ADR 0011](0011-the-server-keeps-the-clock.md).
  - *Length left* counts from the resume point and leaves out skipped segments
    ([ADR 0024](0024-skip-segments-at-playback.md)). A 40-minute video with 5 minutes to go fits a 10-minute window.
  - *Grace* is a per-profile setting, default 2 minutes.
- **Where it runs.** On the server, as the last step of the visibility pipeline
  ([ADR 0022](0022-one-visibility-pipeline-for-rules.md)). The app never filters by itself.
- **When it applies.** Whenever a limit is running. With no limit at all, everything approved is shown. A per-profile
  switch can turn the rule off and fall back to "stop at time-up".
- **Refresh.** The app refetches rows when a video ends, when it returns to the home screen, and every minute. Items
  that no longer fit drop out.
- **A started video finishes.** If an item fitted when it started, it plays to its end.
  - Against **watched-time** limits (daily allowance, session), pausing costs nothing, so a fitted video still fits.
  - Against **wall-clock** limits (a one-off limit, a schedule), a pause can push the end past the limit. The video
    may then run over by at most a hard cap (default 10 minutes), after which it stops.
- **The last pick.** When fewer than a set number of items fit, the home screen becomes "One more: pick one" with up to
  three choices. When nothing fits, the time-up flow starts early.
- **No dead ends.** If another rule (learn-first, a category budget) would leave nothing playable while time remains,
  that rule is waived for the rest of the session and the parent sees a note. Time-fit itself is never waived.
- **Items without a length.** Live TV and looping channels are hidden while a limit is running, unless the profile
  allows "live until time-up", in which case they are cut at time-up.
- **Autoplay.** "Up next" only chains items that fit ([ADR 0013](0013-parents-build-the-home-screen.md)).
- **Fill the time.** A parent can ask for a playlist that fits the limit to the minute: a simple packing over approved
  items for that profile, optionally by tag.
- Long items are covered in [ADR 0028](0028-long-items-parts-and-movie-night.md).

## Consequences

- Limits end at the end of a video, which is the point.
- Near the end of a session the choice gets small, and favorites may vanish. The "last pick" screen makes that a
  choice and not an empty page.
- With a wall-clock limit a child can stretch a session a little with pause. The hard cap bounds it.
- Lengths must be right for every source. Plex and Jellyfin report them; local files are probed at download.

## Alternatives

Stop exactly at time-up: simple, and the cause of the fight. Warn only ("this won't finish"): a 2- and a 4-year-old
will not act on it. Filter in the app: the rule would be skippable and would differ per client.

## Where it lives

`server/app/limits/timefit.py`, `server/app/curation/fill.py`.
