# 0002. Scope: one household, home network, Android TV first

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The goal is a replacement for YouTube Kids for the two boys: only approved videos, no ads, no algorithm, with time
limits their parents control. The owner asked to plan for the Android TVs only for now.

## Decision

- The system serves one household on the home network. It is not reachable from the internet.
- The only kid-facing client in scope is an Android TV app (Chromecast with Google TV and similar). Tablets, phones and
  iPad are out of scope until a later ADR.
- The parent side is a web page that works on a phone and a computer.
- The project is private. `kidtube` is a working name for the folder only.
- If it is ever made public, it ships under its own name and icon and without any Google artwork
  ([ADR 0016](0016-match-the-youtube-kids-look.md)), and a new ADR covers what else changes.

## Consequences

- No accounts, cloud relay or multi-household design. That removes a lot of work.
- Travel and tablet ideas (offline cache, travel mode, pick-on-tablet) wait.
- Decisions that would block a later public release are avoided where that is cheap, but not at any cost.

## Alternatives

Design for public release from day one, as WhatsOn ended up: slower, and the look-alike goal conflicts with it.
Include tablets now: doubles the client work before the idea is proven.

## Where it lives

Whole project. Idea list: `docs/ideas.md`.
