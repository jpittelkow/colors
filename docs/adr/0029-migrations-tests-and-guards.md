# 0029. Database migrations, tests, and guard tests for the rules

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The audit found no ADR for how the database changes over time or how we know the rules hold. The costly failure in
this project is a video reaching a child that should not have: a new endpoint that forgets the pipeline, or a
migration that resets approvals.

## Decision

- **Migrations.** Schema changes are numbered SQL migrations applied at start-up, each in a transaction. Before
  applying any, the server takes an online backup of the database into the appdata folder and keeps the last few.
- **Restore** is documented and tried once before the boys rely on the app: stop the container, put back the database
  file, start, rescan the library ([ADR 0005](0005-files-on-disk-layout-format-retention.md)).
- **Tests.** Server logic is tested with pytest: limits and time-fit against a fake clock, the pipeline steps one by
  one, download rules against recorded yt-dlp output (no network in tests).
- **Guard tests**, in the style of WhatsOn's, fail the build when a rule of the design is broken:
  - every route under `/api/tv/` that returns items or a stream goes through the pipeline
    ([ADR 0022](0022-one-visibility-pipeline-for-rules.md));
  - no TV response contains a media-server token, a file path or an unsigned stream URL;
  - nothing outside `server/app/ai/` calls a model, and nothing in it changes approval
    ([ADR 0014](0014-ai-is-optional-and-only-advises.md)).
- **The TV app** has unit tests for the player's skip and part logic and screenshot tests of the main screens against
  the reference ([ADR 0016](0016-match-the-youtube-kids-look.md)).

## Consequences

- The rules that matter are checked by the build, not by memory.
- Guard tests need upkeep when the code is reorganised.
- Screenshot tests are brittle; they cover a handful of screens only.

## Alternatives

Create tables on start and alter by hand: fine until the first real change loses data. Tests only where bugs appear:
the first missed pipeline check would be found by a child.

## Where it lives

`server/migrations/`, `server/tests/` (`test_guards.py`), `tv/app/src/test/`, `docs/runbooks/restore.md`.
