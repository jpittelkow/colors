# 0018. Pairing a TV, the parent gate and the admin password

- **Status:** Accepted
- **Date:** 2026-11-22 (revised the same day after the audit; keeping kids inside the app moved to ADR 0027)

## Context

The TVs must be tied to the server, and parents need a way into settings on the TV that a child will not open by
accident.

## Decision

- **Pairing.** A new TV shows a short code. A parent types it in the admin page, names the TV, and the server issues a
  device token. The app stores it in Android's encrypted storage. A parent can revoke a TV in the admin page.
- **Finding the server.** The app looks for the server on the network (mDNS) and falls back to a typed address.
- **Parent gate on the TV.** A numeric passcode set in the admin page, entered with the remote. It opens the grown-up
  profile, app settings, updates and exit.
- **Admin page.** Protected by a password by default. A parent may turn it off. This differs from WhatsOn's no-login
  rule; the reason is to keep the habit for when the boys are older, not a present risk
  ([ADR 0027](0027-keeping-kids-inside-the-app.md)).
- A forgotten passcode is reset from the admin page.

## Consequences

- A paired TV cannot be swapped for another client without a parent.
- One more password for the parents.

## Alternatives

No pairing (any device on the network may ask): simple, but a revoked or unknown device could not be told apart. No
admin password, as in WhatsOn: fine today at ages 2 and 4, a gap later.

## Where it lives

`server/app/devices/` (`pairing.py`), `tv/` (`pairing/`, `gate/`).
