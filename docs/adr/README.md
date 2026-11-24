# Architecture Decision Records

Each file records one design decision: the situation, what was decided, and what it costs. Same format as WhatsOn.
Copy `template.md` to `NNNN-short-title.md` for a new one. Never rewrite an accepted ADR's reasoning; replace it with a
new ADR.

**Status** is one of `Proposed`, `Accepted`, `Rejected`, `Deprecated` or `Superseded by ADR NNNN`.

All of 0002–0029 were written on 2026-11-22 before any code and were **accepted by the owner on 2026-11-22**. They were
audited and revised the same day; see [`../adr-audit-2026-11-22.md`](../adr-audit-2026-11-22.md).
Idea ids refer to [`../ideas.md`](../ideas.md).

| No. | Decision | Status | Ideas covered |
|---|---|---|---|
| [0001](0001-record-decisions-as-adrs.md) | Record decisions as ADRs | Accepted | |
| [0002](0002-scope-home-only-android-tv-first.md) | One household, home network, Android TV first | Accepted | I3, I4 |
| [0003](0003-one-server-fastapi-sqlite-new-codebase.md) | One FastAPI + SQLite server, new codebase (not a fork) | Accepted | I1 |
| [0004](0004-download-with-ytdlp-queue-and-schedule.md) | yt-dlp search, add by URL, subscriptions, job queue | Accepted | A1–A3, A5–A8, B1–B3, B8 |
| [0005](0005-files-on-disk-layout-format-retention.md) | File layout, one playback format, retention | Accepted | B4, B6, B7, B9, B11, B12 |
| [0006](0006-the-server-streams-its-own-videos.md) | The server streams its own videos | Accepted | I2 |
| [0007](0007-sources-contract-one-item-model.md) | Sources contract and one item model | Accepted | A9, D10, J11, J15–J17, J24 |
| [0008](0008-plex-and-jellyfin-allow-listed-streamed-in-place.md) | Plex and Jellyfin: allow-listed, streamed in place | Accepted | J12–J14 |
| [0009](0009-nothing-is-shown-unless-approved.md) | Nothing is shown unless approved | Accepted | A4, A10, D11, D12, J30 |
| [0010](0010-profiles-and-who-can-see-what.md) | Profiles and per-profile content | Accepted | C1, C2, F2, F14, J10, J27, J32 |
| [0011](0011-the-server-keeps-the-clock.md) | The server keeps the clock | Accepted | C3–C8, C12, J8, J9 |
| [0012](0012-only-show-what-finishes-in-time.md) | Only show what finishes in the time left | Accepted | J1–J5 |
| [0013](0013-parents-build-the-home-screen.md) | Parents build the home screen; recommendations are rules | Accepted | D1–D9, J18 |
| [0014](0014-ai-is-optional-and-only-advises.md) | AI is optional and only advises | Accepted | E1–E10, J23 |
| [0015](0015-native-android-tv-app-compose-and-media3.md) | Native Android TV app | Accepted | F13 |
| [0016](0016-match-the-youtube-kids-look.md) | Match a kids profile in the YouTube TV app; own name and artwork; built for non-readers | Accepted | F1, F3, F6, F8, F9, I5, J18–J21 |
| [0017](0017-the-tv-app-is-a-thin-client.md) | The TV app is a thin client | Accepted | F4, F5 |
| [0018](0018-pairing-parent-gate-and-kiosk.md) | Pairing a TV, parent gate, admin password | Accepted | C9, J20 |
| [0019](0019-control-the-app-over-its-own-connection.md) | Control through the app's own connection | Accepted | C7, G1–G3, G5 |
| [0020](0020-home-assistant-through-a-plain-api.md) | Home Assistant through a plain API and webhooks | Accepted | C8, G4, G6, J31 |
| [0021](0021-watch-history-stays-home.md) | Watch history is a local event log | Accepted | H1–H4 |
| [0022](0022-one-visibility-pipeline-for-rules.md) | One visibility pipeline for all rules | Accepted | C10, C11, J22, J25 |
| [0023](0023-one-docker-container-and-alerts.md) | One container on the home server, with alerts | Accepted | B10, G8 |
| [0024](0024-skip-segments-at-playback.md) | Skip segments at playback | Accepted | B5 |
| [0025](0025-admin-page-plain-javascript-installable.md) | Admin page: plain JavaScript, installable | Accepted | A5, A6 |
| [0026](0026-build-order.md) | Build order | Accepted | I6 |
| [0027](0027-keeping-kids-inside-the-app.md) | Keeping kids inside the app, sized for ages 2 and 4 | Accepted | F12, G7 |
| [0028](0028-long-items-parts-and-movie-night.md) | Long items: parts and the movie-night pass | Accepted | J6, J7 |
| [0029](0029-migrations-tests-and-guards.md) | Migrations, tests and guard tests | Accepted | |
| [0030](0030-channel-pictures-everywhere.md) | Channel pictures everywhere, fetched once and cached | Accepted | |
| [0031](0031-loading-states.md) | Loading states: skeletons and a spinner | Accepted | |
| [0032](0032-jobs-page-and-activity-popup.md) | A jobs page and a background-activity popup | Accepted | B1, B10 |
| [0033](0033-light-dark-system-theme.md) | Light, dark or system theme, chosen in the page | Accepted | |
| [0034](0034-ai-through-openrouter.md) | AI through OpenRouter: parent suggestions, a picked-for-you row | Accepted | E1, E2, E5, E10 |
| [0035](0035-importing-what-is-already-approved.md) | Importing what the boys already have approved | Accepted | A7 |
| [0036](0036-profile-avatars.md) | Profile avatars: our own illustrated characters | Accepted | C1, F2 |
| [0037](0037-navigation-by-what-a-parent-does.md) | The parents' page is organised by what a parent does, with a desktop layout | Accepted | Revised 2026-11-23: Downloads and Jobs in the nav, household in Settings |
| [0038](0038-the-name-is-colors.md) | The app is called "colors" | Accepted | F1 |
| [0039](0039-qr-codes-on-the-tv-open-the-parents-page.md) | QR codes on the TV open the parents' page | Accepted | F9 |
| [0040](0040-spoken-lines-are-recorded-files.md) | The TV's spoken lines are recorded files in the kids app's voice | Accepted | F9 |

## Not decided yet

These ideas have no ADR and need one before they are built: Shorts-style feed (F7), offline cache and travel (F10,
J28), tablets and pick-on-tablet (F11, J29), break prompts (J26), the family channel's upload path (J24), HTTPS for the admin page and the TV app, and proxying
Plex or Jellyfin transcodes.
