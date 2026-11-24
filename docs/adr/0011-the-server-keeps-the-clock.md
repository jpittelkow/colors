# 0011. The server keeps the clock: allowances, sessions and schedules

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Time limits must hold across every TV, survive an app restart, and be changeable from a parent's phone in the middle
of a video. kidplex kept lockout and session timers on its server for the same reason.

## Decision

- All time accounting is on the server, per profile. The TV app only reports and obeys.
- Three limits, each optional, and the tightest one applies:
  - **Daily allowance**: minutes per day, with separate weekday and weekend values.
  - **Session**: at most N minutes in one sitting, then a lockout of M minutes.
  - **Schedule**: hours when the app is closed (bedtime, school mornings).
- A parent can also start a **one-off limit** from the phone ("30 minutes from now"). This is the time limit the owner asked
  for, and it feeds [ADR 0012](0012-only-show-what-finishes-in-time.md).
- **Two kinds of time.** The daily allowance and the session limit count **watched time**. A one-off limit, a lockout
  and a schedule run on the **wall clock**.
- While a video plays, the app sends a heartbeat every 15 seconds with profile, item and position. The server counts
  watched time from heartbeats, so paused time and the home screen do not count. The answer to a heartbeat can carry
  a command (stop, refresh, lock), so limits and hiding work even if the control connection is down.
- The same profile playing on two TVs at once counts on both.
- Every answer from the server carries the profile's **time left** and the reason for it. The app shows or hides the
  timer per profile setting.
- When time runs out the server tells the app to run the time-up flow
  ([ADR 0016](0016-match-the-youtube-kids-look.md)). A video that fitted when it started is allowed to finish
  ([ADR 0012](0012-only-show-what-finishes-in-time.md)).
- Parent actions: add time, end now, "last one" (finish this video, then lock), pause all. Modes that loosen limits
  for a day: vacation (can follow Home Assistant's `input_boolean.vacation_mode`) and sick day.
- Days roll over at a set local time (default 04:00), not midnight.
- If the app cannot reach the server, it plays nothing new and finishes at most the current video.

## Consequences

- One allowance across all TVs; restarting the app or switching TV gains nothing.
- The app is useless when the server is down. That is the safe failure for this project.
- Heartbeats make watch time accurate to about 15 seconds, which is good enough.

## Alternatives

Timers in the app: reset by a force-stop, and not shared between TVs. Android's own screen-time tools: per device and
per app, with no idea what is playing.

## Where it lives

`server/app/limits/` (`clock.py`, `allowance.py`, `schedule.py`), heartbeat in `server/app/api/playback.py`.

## Revision 2026-11-23: "last one" is one video

The owner: "last one" must not let him flick through videos; he can start one more, that's all. Until now it only locked
when any video ended, so a child could start video after video without finishing one.

- Pressed while a video plays, that video is the last one. Otherwise the next video started is.
- The chosen video is kept on the override (`note = "item:<id>"`). Starting any other video is refused
  (`403 lastone`); the same one may be started again (back out and in, resume).
- Home shows only "Your last one", the menu's lists and channel pages show only that video, and up next is empty.
  When it ends the profile locks, as before.
- The parents' page also offers 5 and 10 minute limits.
