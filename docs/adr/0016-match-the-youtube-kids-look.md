# 0016. Match the look of a kids profile in the YouTube TV app, with our own name and artwork

- **Status:** Accepted
- **Date:** 2026-11-22 (revised the same day after the audit; reference changed by the owner)

## Context

The owner wants the TV app to look as close as possible to what the boys know. The standalone YouTube Kids app was removed
from TVs in July 2024. On a TV, YouTube Kids is now a **kids profile inside the main YouTube app**, and that is what
the boys see. The owner chose it as the reference. The boys are 2 and 4 and cannot read.

## Decision

- The reference is **a kids profile in the YouTube app on Google TV**: its home screen, category row, video cards,
  channel page, search, player and controls.
- Before building, we open a kids profile on one of our TVs, capture every screen and state (focused, unfocused,
  loading, empty), and write the screen list and measurements into `docs/design/reference.md`. That file, not memory
  or this ADR, is the source of truth for the look. The build is checked against it screen by screen.
- Screens the reference does not have are **our own design in the same style**: "Who's watching?" with our profiles,
  the timer, the "one more" pick, the time-up screen, locked cards, the parent gate.
- **Built for non-readers.** Nothing a child must do depends on reading:
  - cards are pictures first; categories and rows have icons;
  - search is by voice, limited to the local library ([ADR 0014](0014-ai-is-optional-and-only-advises.md));
  - a locked card shows a picture reason (a clock, a book for learn-first), and time-up and "one more" are spoken as
    well as shown.
- All **assets are our own**: icon, wordmark, avatars, sounds, illustrations, fonts with a licence that allows it. The
  app does not use the YouTube or YouTube Kids name, logo or other Google artwork, and has its own name on the TV's
  home screen.
- Thumbnails, channel names and channel avatars are the real ones from the downloaded videos.
- Design values (colours, sizes, radii, sounds) live in one theme file, so the look can be changed in one place if the
  project is ever made public ([ADR 0002](0002-scope-home-only-android-tv-first.md)).

## Consequences

- The boys get the layout they already know. At 2 and 4 the name and logo will not register.
- YouTube will keep changing its app. We match a snapshot and do not chase it.
- Our added screens have no reference, so they need design work of their own.
- Spoken prompts need recorded or generated audio, one more asset set to maintain.

## Alternatives

The phone/tablet YouTube Kids app adapted to a remote: more playful, but never existed on TV in that form and is not
what the boys see. Use YouTube's logo and name: not something we ship. An original design: loses the familiarity.

## Where it lives

`tv/` (`ui/theme/`, `ui/home/`, `ui/player/`, `ui/timeup/`), `docs/design/reference.md`.
