# 0019. Control the TV through the app's own connection to the server

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Parents want to see what is playing on each TV and act from a phone: pause, stop, "last one", send a message, start a
video for the boys. WhatsOn does this from outside with `androidtvremote2` and deep links because it does not own the
app on the TV. Here we do.

## Decision

- While it runs, the app keeps one **WebSocket** open to the server, authenticated with its device token.
- The app reports state on it: profile, item, position, playing or paused, volume. This is the **now-playing** data in
  the admin page, and it is exact, unlike WhatsOn's best guess.
- The server sends commands on it:
  - `pause`, `resume`, `stop`, `seek`, `next`;
  - `play` an item or playlist for a profile ("put this on for them");
  - `refresh` (rules or rows changed);
  - `message` (a short text over the video: "dinner in 5 minutes");
  - `overlay` (a picture or live view, for a doorbell);
  - `lock` and `unlock`, `last_one`, `volume_cap`.
- **A parent's `play` is an override.** It must still be an approved item, but it skips the open-hours, optional-rule
  and time-fit steps of the pipeline ([ADR 0022](0022-one-visibility-pipeline-for-rules.md)). It is logged as a
  parent action, and the time watched still counts against the allowance.
- Commands are obeyed only from the server. There is no open port on the TV.
- If the socket drops, the app reconnects with backoff and falls back to the heartbeat
  ([ADR 0011](0011-the-server-keeps-the-clock.md)) for limits, so limits hold without it.
- Waking a sleeping TV or switching input is outside this channel. If needed later, it reuses WhatsOn's TV driver as
  a separate, optional piece.

## Consequences

- Control is instant and needs no pairing with Android's remote service, no adb and no Home Assistant.
- It only works while the app is running in the foreground. A TV showing something else cannot be controlled this way.
- Overlays inside our app replace the need for a separate overlay app's pop-up on the kids' TVs while the app is open.

## Alternatives

`androidtvremote2` key presses as in WhatsOn: blind, and cannot show state. Polling: slow for pause and messages.

## Where it lives

`server/app/api/tv/socket.py`, `server/app/control/`, `tv/` (`net/ControlSocket.kt`).
