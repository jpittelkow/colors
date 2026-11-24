# 0032. A jobs page and a background-activity popup

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The server does work in the background: downloads, subscription checks, retention, Plex refresh. A parent can't
see any of it except on the Downloads screen. The owner's earlier download manager has two things that work well and the owner asked for
them here: a jobs page listing every scheduled task with "Run now", and a small floating panel that shows what is
running from every screen.

## Decision

- **Scheduled jobs get names and a record.** A `job_runs` table records each run of a named job: started, finished,
  result, error. The jobs are:
  - check all subscriptions (and each subscription on its own schedule),
  - delete what retention rules no longer keep,
  - refresh allowed Plex shows,
  - refresh channel pictures (ADR 0030),
  - check for a newer yt-dlp (report only; updating means rebuilding the image),
  - AI suggestions (ADR 0034), when AI is on.
- **The Jobs page** (More › Jobs) lists each job: what it does in one line, last run and its result, next run, and
  a **Run now** button. A running job shows a spinner and can be stopped where stopping is safe. Below it, the
  download queue (now, next, failed with Try again), which replaces the separate Downloads screen.
- **The activity popup** is a small pill fixed above the bottom bar on every screen. It shows only when something is
  happening or wrong: "Downloading 2 · 64%", "Checking channels", or "3 failed" in red. Tapping it opens a panel with
  the running jobs, the current downloads with progress, and the latest errors, each linking to the Jobs page.
  It polls `/api/admin/activity` every 3 seconds while visible and every 15 seconds when nothing is running.
- Pause downloads and pause checks are switches on the Jobs page.

## Consequences

- A parent can see and drive all background work from one place, and notices failures without looking.
- Polling every few seconds from an open phone page. The activity call is one small query.
- One more table; old runs are trimmed to the last 200 per job.

## Alternatives

Server-sent events for live progress: smoother, but more to build and keep open on a phone; polling is enough here.
Only the Downloads screen: what we have, and failures go unseen.

## Where it lives

`server/app/jobs_registry.py`, `server/migrations/0003_*.sql` (`job_runs`), `server/app/api/manage.py`
(`/activity`, `/jobs/...`), `server/app/static/admin/app.js`. Amends ADR 0004 (the queue now shows on Jobs).

## Revision, 2026-11-23 (after the owner tried it)

The first build put scheduled jobs and the download queue on one page and showed the pill only when something
was happening. The owner: it "does not work well at all" and should be dedicated to downloads, like that download manager. What
changed, modelled on an earlier download manager's pipeline panel and its "scrobbler" pill:

- **Downloads is its own page** (More › Downloads). Each running download is a card with thumbnail, title,
  channel, a progress bar and one line: percent, size so far and total, speed, time left. Stages without a
  percentage (getting ready, joining picture and sound, finishing, checking) show as a pulsing label. Each card has
  **Stop**. Below: **Up next** (take one out of the queue), then a **History** with All / Done / Failed / Stopped,
  search, pages, and Try again. Pause downloads and Retry all failed sit at the top.
- **Live numbers are kept in memory** (`downloads/progress.py`), fed by yt-dlp's progress and post-processing
  hooks a few times a second. Only a coarse percentage still goes to the database.
- **Stop** raises inside the download hook, removes the half-downloaded pieces, and marks the job `stopped`, which
  is not a failure: it is left out of failure counts and of Retry all failed.
- **Jobs is the scheduled work only** (More › Jobs): status, last run with how long it took, next run, Run now or
  Stop, and an editable "every N minutes/hours/days" per job. A new job retries failed downloads every 6 hours and
  gives up after 3 tries.
- **The pill is always there**: a dot (pulsing while working, yellow when paused, red on errors), a label and a
  count, bottom right above the bar; on a phone it shrinks to the dot when all is quiet. Tapping it opens a panel
  with running jobs and how long they have run, anything that needs a look, up to four downloads with small bars,
  and links to Downloads and Jobs. Both are built once and updated in place, so the panel stays open and steady.
- Lists on these pages update in place by key rather than being redrawn, so a button is never replaced under a
  finger.

Also fixed here: a video added while YouTube left out its channel was filed under "unknown", so its channel had
no picture or link. Adding now looks twice, a finished download moves the video to its real channel, and the
daily pictures job repairs older ones.

**Quick retries, added the same evening.** One download in 23 on the live server failed with "This video is
not available", and the same video downloaded fine an hour later: YouTube refuses a request now and then for no
lasting reason. A failed download now waits and tries again by itself, after 1 minute and then after 5 more,
and only counts as failed after three tries in a row. The Downloads page shows "YouTube refused it. Trying again
in 4 min" on the waiting row. The 6-hourly retry job still picks up what is left, up to six tries in all; a
parent's Try again starts the count afresh.
