# 0044. A screen between videos: watch again, up next in 5, more below

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

With autoplay on, the next video starts the moment one ends ([ADR 0013](0013-parents-build-the-home-screen.md)). A
child gets no moment to say "again!", to see what's coming, or to pick something else, and a parent watching can't
tell a chosen video from an autoplayed one. Jeff asked for a screen between videos: what was just played, with a way
to replay it; what is next; a 5-second countdown; and other suggestions. If nobody presses anything, the next video
plays. Any press stops the countdown.

The app already has what this needs. When a video starts, the player asks `/upnext` for the per-child autoplay count
and an ordered list of videos that fit the time left (ADR 0012). When a video ends, it tells the server and either
plays the first of those or goes back to the rows.

## Decision

- **When it shows:** a video has ended, the server's answer to the "ended" heartbeat doesn't say stop, and autoplay
  would have played the next one (`chain + 1 < autoplay_n` and `/upnext` has a video). That is exactly the moment the
  player now jumps straight to the next video; the screen goes in between. With autoplay off, or at the end of the
  chain, nothing changes: back to the rows.
- **What it shows**, on a 1920×1080 frame (see the mockup):
  - **Up next**, the largest thing on the screen: the first video `/upnext` returned, with its picture, title,
    channel and length. A ring around its play button empties over **5 seconds**, with the number in the middle.
  - **You watched**: the video that just ended, smaller, beside it, with a **Watch again** button.
  - **More to watch** underneath: one row of the rest of the `/upnext` list (up to 12), same channel first.
  - **Back** in the corner, to the rows.
- **The countdown:** 5 seconds, fixed. When it reaches 0, the next video plays as an autoplay step (`chain + 1`).
  It doesn't count as watch time, because only playing counts (ADR 0011).
- **Any press stops it.** The first key of any kind stops the countdown for good: the ring and number go away and
  the card says "Pick one". The key still does its usual job: OK on **Up next** (where the focus starts) plays it now,
  the arrows move the focus, and Back goes to the rows. Nothing starts by itself after that.
- **A choice starts a new chain.** Watch again, Up next pressed by hand, or a card from the row count as the child's
  own pick, just like picking from the rows: the chain resets to 0. Only the countdown adds to the chain, so "stop
  after N videos in a row" still means N videos nobody chose.
- **Watch again** starts the video from the beginning, not from the saved end point.
- **Left alone after a press:** after 2 minutes with no key, the screen goes back to the rows, so a TV nobody is
  watching doesn't sit on a static picture.
- **The server's rules still decide.** Everything on the screen comes from `/upnext`, which only lists videos that
  are allowed and fit. Pressing play still asks `/play`, which checks again ([ADR 0017](0017-the-tv-app-is-a-thin-client.md)).
  If time runs out on this screen, a parent presses End now, or the limit stamp changes (the TV polls it every few
  seconds), the screen gives way to the Stopped screen, as the rows do.
- **Last one:** when "last one" is on, the video that ended was the last, so no screen. The player stops as it does now.
- **No server change** beyond what `/upnext` already returns (the 24-video list since the overlay got its rows).

## Consequences

- The boys can replay a favourite or see what's coming without having to stop the next video first. Parents can
  still let it run on its own.
- Every autoplay step takes 5 seconds longer.
- A child who presses a key to see the countdown then has to pick. That's intended: once he's pressing buttons, he
  is choosing.
- One more screen in the TV app (`ui/Between.kt`), and the player's end-of-video handler changes.

## Alternatives

- **YouTube's corner card** (a small "Up next" over the end of the video, with a cancel button): less interruption,
  but the boys can't read "cancel", there's no Watch again and no other suggestions, and it covers the picture
  (static over video was ruled out for OLED burn-in in the player).
- **A parent-set countdown length (0-30 s):** possible later as a Limits field next to autoplay. Fixed at 5 s until
  someone needs something else.
- **Show the screen with autoplay off too, without the countdown:** a "what now?" screen after every video. Left out
  for now, since autoplay off was chosen to mean "back to the rows".
- **Pause the countdown while a key is held, then resume it:** too subtle for a four-year-old. One press stops it.

## Where it lives

`tv/app/src/main/java/app/colors/tv/ui/Between.kt` (the screen), `ui/Player.kt` (end of video → Between; `fromStart`
for Watch again), `ui/Screens.kt` (`Screen.Between`), `MainActivity.kt`. TV app 0.5.0. Mockup:
`docs/design/between-videos.html`. Related: ADR 0011, 0012, 0013, 0017.
