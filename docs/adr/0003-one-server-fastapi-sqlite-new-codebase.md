# 0003. One server process: FastAPI and SQLite, a new codebase

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The server manages profiles, downloads, the library, curation, time limits and the API the TV app uses. Two existing
projects overlap: an earlier yt-dlp download manager (channels, yt-dlp jobs, scheduler, logs, settings) and WhatsOn (search, sources, TV
control, AI, a phone-first interface). Both are single FastAPI processes with SQLite.

## Decision

- One Python FastAPI process, one SQLite database (WAL mode), background work on in-process workers and a scheduler.
- A **new codebase**, not a fork. that manager is built around syncing to another media app, which
  this project does not need. We copy its proven parts: yt-dlp as a library, the job pipeline, download progress,
  yt-dlp self-update, the cookies file handling.
- From WhatsOn we take the `Source` contract idea ([ADR 0007](0007-sources-contract-one-item-model.md)), the
  optional-AI rule ([ADR 0014](0014-ai-is-optional-and-only-advises.md)) and the no-build-step interface
  ([ADR 0025](0025-admin-page-plain-javascript-installable.md)).
- Settings that change at runtime live in the database and are edited in the admin page. Environment variables are
  only for paths, the port and first-run secrets.

## Consequences

- One container to run and back up. One language on the server.
- A single process means a crash stops downloads and the API together. Acceptable at home; jobs resume on restart.
- SQLite limits us to one writer at a time. Fine for one household.
- Code copied from it will drift from its origin. We accept that.

## Alternatives

Fork an existing download manager: fast start, then a long fight removing what it was built around. Pinchflat or Tube Archivist plus a thin layer: no
control over approval, profiles or time limits, which are the point. Separate download and API services: more parts
for no gain at this size.

## Where it lives

`server/` (`server/app/main.py`, `server/app/db.py`).
