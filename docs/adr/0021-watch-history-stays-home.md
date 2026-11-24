# 0021. Watch history is an event log that stays at home

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Parents want to know what each boy watches: totals, favorites, what gets skipped, whether one channel is taking over.
Several rules also need history (repeat limits, category budgets, learn-first). This is data about children.

## Decision

- The server keeps an append-only **event log** per profile: started, progress, finished, skipped (left before a set
  share was watched), liked, favorited, wished, refused (with the rule that refused it).
- Watch state (resume point, watched) and daily totals are derived from the log and stored for speed.
- The admin page shows, per child: time by day, by container, by tag and by source; finished against skipped;
  most rewatched; and simple trend flags (one container above a share of the week, daily time rising).
- The log lives only in the server's database. It is not sent to any outside service. AI features that use it run
  against a local model, or get totals without names ([ADR 0014](0014-ai-is-optional-and-only-advises.md)).
- Plex and Jellyfin get only the watch progress they need ([ADR 0008](0008-plex-and-jellyfin-allow-listed-streamed-in-place.md)).
- Raw events are kept for a year by default, then reduced to daily totals. A parent can clear a profile's history.
- The database is backed up with the rest of the appdata. Project docs and journals never contain the boys' history.

## Consequences

- Rules and reports share one source of facts.
- The log grows; the yearly reduction keeps it small.
- Stats can tempt over-watching the watchers. The digest is weekly by default.

## Alternatives

Only keep resume points: no reports and no history-based rules. Send to Trakt or similar: children's data leaves the
house.

## Where it lives

`server/app/history/` (`events.py`, `rollup.py`, `reports.py`).

## Revision 2026-11-23: what is built

- **Built:** each boy's page shows his week (minutes per day, most-watched channels, videos on repeat) and his
  **history**: every play, newest first, under a heading per day, with the time, channel, TV and "Watched to the
  end"; 30 at a time with "Show older" (`GET /api/admin/history`). **Clear his history** (`DELETE /api/admin/history`)
  removes his plays and his resume points / watched marks; minutes per day stay so today's limit still counts, and
  parent actions stay in the log.
- **Not built yet:** progress, skipped, liked, favorited, wished and refused events (only started and finished are
  logged); the yearly reduction to daily totals; the `server/app/history/` module (the code is in
  `server/app/api/manage.py`).
- **Outside services:** ADR 0034 later allowed the AI to send video titles and channel names (never names or
  birthdays) to OpenRouter when AI is switched on; the page says so under the history.
