# 0023. Run as one Docker container on the home server, with alerts

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The household's services run as containers on the Unraid home server, deployed with a script, watched by Uptime
Kuma, with Telegram for alerts. The HA box has no room for this.

## Decision

- One Docker image for the server, run as a compose stack on the home server, deployed with `bash scripts/deploy.sh` like the
  other home projects.
- Volumes: appdata (database, settings, cookies file, yt-dlp updates, the TV app's APK) and the media library share.
  Exact paths and the port are chosen at first deploy, after checking what is free, and written into the runbook, not
  into this ADR.
- The container runs on CPU. Passing in the iGPU is optional and off by default
  ([ADR 0005](0005-files-on-disk-layout-format-retention.md)).
- A `/healthz` endpoint for Uptime Kuma.
- **Alerts** go out through one notifier (Telegram first): repeated download failures, low disk or size cap reached,
  Plex or Jellyfin unreachable, a TV failing its token check, yt-dlp update available after failures.
- The database is backed up by the existing appdata backup, using SQLite's online backup so the copy is consistent.
- Secrets (media server tokens, AI keys, the notifier token) are stored on the server only and never sent to the TV
  app or written into docs.

## Consequences

- Same shape as the household's other services, so the same habits apply.
- Everything depends on the home server. When it is down, the kids' app is down.
- Large downloads and conversions compete with Plex and the other services for disk and CPU. Queues are sequential and low
  priority by default for that reason.

## Alternatives

Run on the HA box: about 4 GB of memory in total, no room. Several containers (API, worker, transcoder): more to run
for no benefit at this size.

## Where it lives

`Dockerfile`, `docker-compose.yml`, `scripts/deploy.sh`, `server/app/notify.py`, `docs/runbooks/deploy.md`.
