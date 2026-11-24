# 0027. Keeping kids inside the app: sized for a 2- and a 4-year-old

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The app only helps if the boys do not end up in the real YouTube. How much lock-down is worth doing depends on who we
are defending against. The boys are 2 and 4. They cannot read, type a passcode, or find their way through Android
settings. They can press buttons on a remote, including Home and the YouTube button, and pick a big icon.

The audit found two options in the first draft that do not work: lock task mode needs the app to be device owner
(in practice a factory reset of the TV), and Google TV has no setting to choose a home app.

## Decision

- **What we defend against:** accidental and curious button presses by small children. Not a child who can read,
  search settings or use another device. This is reviewed when the older boy turns 6, or sooner if he gets around it.
- **Profile hopping is accepted** (the owner, 2026-11-22). Switching to a brother's or the guest profile is not blocked
  ([ADR 0010](0010-profiles-and-who-can-see-what.md)).
- **Lock-down is a runbook, done over adb on each kids' TV**, with a matching revert script, as on the office TCL TV:
  1. Disable the real YouTube apps on that TV (YouTube, YouTube Kids, YouTube Music if present).
  2. Remap or neutralise the remote's YouTube button where the device allows it.
  3. Optionally make our app what Home returns to. On Google TV this is an adb change or a launcher such as
     Projectivy starting our app; it is decided per TV. One Chromecast keeps Projectivy on Home by the owner's
     earlier choice.
- **Optional network rule** on UniFi blocking YouTube for a kids' TV, for when step 1 is undone by a system update.
- The app itself never runs adb or changes the TV's settings. It has no kiosk mode.
- Lock-down happens once limits are in daily use (milestone 2 in [ADR 0026](0026-build-order.md)), not before.

## Consequences

- Cheap to do and easy to undo, and enough for these ages.
- A system update can re-enable apps. The script is safe to run again, and the network rule covers the gap.
- A shared family TV cannot have YouTube disabled without affecting the adults. On such a TV the only protection is
  supervision and the network rule.
- adb on a Chromecast needs Wireless debugging, which a Wi-Fi drop turns off.

## Alternatives

Device owner and lock task mode: the strongest option, needs each TV reset and set up without a Google account
first. Nothing at all: one press of the YouTube button leaves the app.

## Where it lives

`docs/runbooks/lock-down-a-tv.md`, `scripts/tv/apply.sh`, `scripts/tv/revert.sh`.
