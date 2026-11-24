# 0017. The TV app is a thin client; the server decides what is visible

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Rules about what a child may see (approval, profile, schedules, time-fit, learn-first) change often and must be the
same on every TV. An APK is slow to update on several devices.

## Decision

- The server sends **finished screens**: the home screen as ordered rows of cards, a container page, search results,
  up next. Each card has what is needed to draw it and a play reference.
- The app asks for playback with `POST /play`. The server checks every rule again at that moment and answers with a
  stream URL, the resume point, segments to skip, subtitles and the next refresh time, or with a refusal and a reason
  the app can show.
- The app never decides visibility, never filters lists, and never builds a stream URL itself.
- The app keeps only a short-lived cache of the last screens for speed. Nothing is playable from cache.
- One versioned API (`/api/tv/v1`). The server keeps the previous version working until every TV has updated.
- Favorites, likes and wishes are sent as events. The server owns the state.

## Consequences

- New rules, rows and limits ship with a server update only.
- Every rule is enforced in one place, twice: when listing and when playing.
- The app needs the server for everything. No offline use; travel and offline cache would need a new ADR.
- The server does more work per screen. Small for one household.

## Alternatives

A smart client that syncs the library and applies rules locally: works offline, but rules drift between app versions
and can be bypassed on the device.

## Where it lives

`server/app/api/tv/` (`home.py`, `browse.py`, `play.py`, `events.py`), `tv/` (`net/`).
