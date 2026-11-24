# 0026. Build order: a working slice first, then widen

- **Status:** Accepted
- **Date:** 2026-11-22 (revised the same day after the audit)

## Context

The owner wants every idea on the list. Building them all before the boys use anything risks months of work on the wrong
thing. The riskiest parts are the TV app's playback and look, and time-fit.

## Decision

Build in milestones that each end with something the boys or parents use. Idea ids refer to `docs/ideas.md`.

1. **M1: watch one approved video.** Server skeleton, migrations and guard tests, add by URL and search with preview,
   download queue, approve, assign to a profile, tag by hand, stream. TV app: pairing, profile picker, home rows,
   player, resume, self-update, no ads or links out. (A1, A2, A4, B1, B8, B9, C1, C2, D1, F1, F2, F5, F8, F13)
2. **M2: limits.** Server clock shared across TVs, daily and one-off limits, time-fit, time-up flow, parent gate,
   "last one", add time. Then the lock-down runbook on the kids' TVs
   ([ADR 0027](0027-keeping-kids-inside-the-app.md)). (C3–C6, C9, J1–J5, J8, J9, F9, F12, G7)
3. **M3: subscriptions and the inbox.** Channel rules, schedule, trusted channels, block list, alerts, retention,
   conversion, skip segments, subtitles. (A3, A10, B2–B7, B10–B12, D12, J30)
4. **M4: the look.** Capture the reference screens and match them: category row, sounds, channel pages, voice search,
   favorites, grown-up profile. (A9, F3, F4, F6, F14, J18–J21)
5. **M5: Plex and Jellyfin.** Sources, allow-list, direct-play check, watch sync, movies tab, parts and movie-night
   pass. (D10, J6, J7, J11–J14)
6. **M6: control and the house.** Control socket, now playing, messages and overlays, Home Assistant API with earned
   time and vacation mode. (C7, C8, C12, G1–G6, G8, J31)
7. **M7: curation depth.** Row editor, dated rows, rested channels, up-next rules, playlists, looping channel, the
   optional rules, reports. (C10, C11, D2–D9, D11, H1–H4, J22, J25, J26)
8. **M8: AI.** Tags, screening, channel report, suggestions, digest, playlist drafts, quizzes. (E1–E10, J23)
9. **Later, each needing its own ADR:** live TV and music sources, family channel, guest and together modes, age-up,
   Shorts-style feed, tablets and travel, phone share and import extras, media-server transcodes. (A5–A8, F7, F10,
   F11, J10, J15–J17, J24, J27–J29, J32)

Hand tagging exists from M1, so the category row in M4 and the tag rules in M7 do not wait for AI in M8.

## Consequences

- The boys can use it after M2. Everything after is improvement on something real.
- The exact look comes fourth. Until then the app is plain. At 2 and 4 that matters little.
- AI comes late. Tagging is by hand until M8, so tags start at channel level.
- The order will change as we learn. Changes go in a new ADR that supersedes this one.

## Alternatives

Server first, app last: nothing to test with the boys for a long time. The look first: polish on top of unproven
playback and limits.

## Where it lives

`docs/roadmap.md` tracks progress against these milestones.
