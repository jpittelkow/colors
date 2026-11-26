# 0043. Trust Home Assistant's login for the parents' page

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The parents' page is also a Home Assistant sidebar panel, proxied by the `hass_ingress` integration at
`/api/ingress/colors/`. Home Assistant has already signed the parent in, so the page's own password
([ADR 0018](0018-pairing-parent-gate-and-kiosk.md)) was a second sign-in. The proxy can add headers to every request.

## Decision

If `<data>/proxy-secret` exists, a request whose `X-Kidtube-Proxy` header equals its contents (constant-time compare)
counts as a signed-in parent. Home Assistant's panel is configured to send that header. Without the file nothing
changes, and opening the server's own address still asks for the password.

## Consequences

- One sign-in when the page is used from Home Assistant.
- Anyone who can read the secret (the data folder, or Home Assistant's stored panel config) can reach the parents' API
  from the network. It is as sensitive as the admin password.
- Signing out from inside Home Assistant does nothing; Home Assistant's own sign-out is the one that matters.
- The file is read at start-up, so changing it needs a restart.

## Alternatives

- Trusting a `Remote-User` header alone: anything on the network could send it.
- Trusting requests from Home Assistant's IP: a container port mapping can hide the source address, and it trusts
  every add-on on that host.
- Turning the password off (the existing setting): would leave the direct address open.

## Where it lives

`server/app/api/admin.py` (`_proxy_trusted`), `server/app/main.py`, `docs/home-assistant/`.
