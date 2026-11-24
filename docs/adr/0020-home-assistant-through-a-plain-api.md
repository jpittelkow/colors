# 0020. Home Assistant talks to a plain API and receives webhooks

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The house runs on Home Assistant. Useful links: screen time on a dashboard, an "everything off" button, pause when the
doorbell rings, lock at the bedtime scene, extra minutes for chores, a vacation switch. The HA box is short on memory,
so nothing heavy can run there.

## Decision

- The server exposes a small **REST API for automation**, with its own API key:
  - read: per profile, minutes used and left today, watching or not, current item, locked or not; per TV, state;
  - act: pause all, lock, unlock, add or remove minutes, last one, send a message, show an overlay, play a playlist,
    set a mode (vacation, sick day).
- The server can call **webhooks** on events: started watching, stopped, time-up, limit reached, wish made, download
  failures, inbox waiting.
- In Home Assistant this is set up with built-in pieces (RESTful sensors, `rest_command`, webhook triggers). An example
  package file ships in `docs/home-assistant/`.
- **Earned time** is an HA automation calling "add minutes". The server only keeps the ledger and shows why minutes
  were added.
- Home Assistant is optional. Nothing in the server depends on it.

## Consequences

- No custom integration to write or maintain, and nothing added to the HA box's memory.
- Sensors update by polling (for example every 30 seconds) unless a webhook pushes sooner.
- Setup in HA is YAML by hand. A proper integration or MQTT discovery could replace it later with a new ADR.

## Alternatives

A custom HA integration: nicer in HA, a second codebase to keep working across HA releases. MQTT discovery: neat, but
adds a broker dependency. Doing time rules in HA: splits the rules across two systems.

## Where it lives

`server/app/api/automation.py`, `server/app/webhooks.py`, `docs/home-assistant/`.
