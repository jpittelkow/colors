# 0039. QR codes on the TV open the parents' page

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Several TV screens ask a parent to do something on their phone: pair the TV, add time, unlock. Until now that
meant opening the parents' page by hand and finding the right screen. The owner, on the first TV mockups: add a QR code
with a link to the parents' app.

## Decision

- The TV app draws a **QR code** on the screens where a parent is likely to reach for a phone. Scanning it with
  the phone's camera opens the parents' page at the right place:
  - **Pairing:** the pairing screen, with this TV's code already filled in (`#tvs/<code>`). The six digits stay
    on screen for typing by hand.
  - **Time's up** and **closed hours:** the page of the boy who is watching (`#kid/<id>`), where "+10 min",
    "Unlock for an hour" and his limits are.
  - **Grown-ups area** (behind the passcode): the parents' page itself.
- The link uses the **server address the TV itself is using**, so it works on any home network without setup.
  It is built on the TV; the server only has to accept the addresses above.
- A QR code carries **no secret**: only an address on the home network. The parents' page still asks for its
  password, and a pairing code is useless without it. So the codes may show on screens the boys can see.
- Drawn dark on a white rounded card with a clear margin, at least 220 px across on a 1080p screen, so a phone
  reads it from the sofa. One short line of words beside it ("Scan with your phone", "For grown-ups").

## Consequences

- Pairing a TV becomes: scan, sign in, name it.
- "More time" is one scan away from the screen that says time is up.
- The parents' page gains one small thing: the pairing screen accepts a code in its address.
- A phone that is not on the home Wi-Fi cannot open the link. That is true of the parents' page in general
  (ADR 0002).

## Alternatives

Only the typed code: works, slower. A QR code that signs the phone in: would put a secret on the TV screen.
Showing the QR on the home screen all the time: clutter the boys do not need.

## Where it lives

`tv/` (pairing, time-up, closed and grown-ups screens), `server/app/static/admin/app.js` (the `#tvs/<code>`
address). Amends ADR 0018 (pairing).
