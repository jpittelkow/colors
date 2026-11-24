# 0025. The admin page: plain JavaScript, no build step, installable on a phone

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Parents run everything from the admin page: search and add, the inbox, rows, profiles, limits, now playing, downloads,
reports. Most of that happens on a phone, often quickly. WhatsOn's plain-JavaScript interface with no build step has
been easy to keep working.

## Decision

- The admin page is served by the server as static files: plain JavaScript modules, HTML and CSS, no framework and no
  build step, as in WhatsOn.
- It is laid out for a phone first and also works on a computer, in light and dark.
- It is an installable web app. Installed on Android, it registers as a **share target**, so "Share" from the YouTube
  app sends a video or channel straight to "add" ([ADR 0004](0004-download-with-ytdlp-queue-and-schedule.md)).
- A **bookmarklet** does the same from a desktop browser.
- Sections: Inbox, Add (search and URL), Library, Home screens (rows), Profiles and limits, Now playing and remote,
  Downloads, Reports, Settings.
- Live parts (now playing, download progress, time left) use server-sent events.
- It talks to the same server API as everything else, under `/api/admin`, behind the admin password
  ([ADR 0018](0018-pairing-parent-gate-and-kiosk.md)).
- Share target and install need a secure context. On the home network that means serving over HTTPS with a local
  certificate or through the existing reverse proxy; which one is decided at deploy.

## Consequences

- Nothing to build or bundle; a change is a file edit.
- No component library. Larger screens (the row editor) need care to stay tidy without a framework.
- The share target only exists on Android phones with the page installed. iPhone users paste a link.
- The server is not reachable from outside the house ([ADR 0002](0002-scope-home-only-android-tv-first.md)), so
  sharing and every other admin action work **only on the home network** (or over the household VPN). Sharing while
  out fails; there is no queue for it.
- How HTTPS is provided also decides whether the TV app talks plain HTTP or must trust a certificate. That choice is
  still open and needs its own ADR before the first deploy.

## Alternatives

React or Svelte with a build: more structure, more tooling to maintain for a home project. Server-rendered pages with
HTMX as in an earlier download manager: fine for forms, weaker for the live and drag-to-order parts.

## Where it lives

`server/app/static/admin/`, `server/app/api/admin/`.
