# 0038. The app is called "colors"

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

"kidtube" was a working name from the first day. ADR 0016 says the app has its own name and artwork and never
uses YouTube's. The owner, on seeing the first TV mockups: call the app "colors".

## Decision

- The name people see is **colors**, lower case: on the TV (the logo top right, the pairing screen, spoken
  prompts) and in the parents' page (the wordmark, the browser tab, the name when installed on a phone).
- **The logo is the word itself, one colour per letter**, in the rounded display face (Fredoka): red, orange,
  yellow, green, blue, purple. On the TV's dark screen the bright tones are used; the parents' page uses slightly
  deeper tones that read on both its light and dark themes. The app icon is six dots in those colours around a
  white play mark on the side panel's indigo.
- **Names nobody sees stay "kidtube" for now**: the project folder and repository, the container and its data
  folder on the home server, the database file, the `KIDTUBE_*` settings and the `kt-` CSS prefix. Renaming a running
  install is a move with its own risks and buys nothing a parent or child would notice. The TV app, not yet
  built, starts life as "colors" (its package name and its name on the TV's home screen).

## Consequences

- One name on every screen a person looks at.
- Two names in the project until the internals are renamed. Documents and code say "kidtube" for the project and
  "colors" for what is on screen.
- "colors" is a common word; searching the web or an app list for it finds other things. It is a home app, so
  that costs nothing.

## Alternatives

Rename everything at once: touches the live container, its template, paths and settings for no visible gain.
Keep "kidtube" on the parents' page only: two names in front of the same people.

## Where it lives

`server/app/static/admin/` (`index.html`, `manifest.webmanifest`, `icon.svg`, `app.js` `wordmark()`, `app.css`),
the TV mockups, and later `tv/`. Amends ADR 0016 (the name).
