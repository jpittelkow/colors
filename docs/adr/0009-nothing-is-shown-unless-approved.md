# 0009. Nothing is shown unless a parent approved it

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The reason for the project is control over what the boys can watch. Subscriptions bring in new uploads without anyone
looking at them, and even a good channel posts the odd bad video.

## Decision

- Every item has an approval state: **waiting**, **approved** or **hidden**. Only approved items can ever reach the TV
  app.
- New items from a subscription land in an **inbox**. A parent approves or hides them, one at a time or in bulk, and
  can preview a video in the admin page first.
- A container can be marked **trusted**: its new items are approved automatically. Trust is per container and is off by
  default.
- A parent can hide any item or whole container from a phone at any time. It disappears from the TV at the next refresh
  and a video that is playing stops.
- A keyword block list is checked against titles, descriptions and transcripts. A match keeps the item in the inbox
  even on a trusted channel, with the reason shown.
- AI screening may add warnings to inbox items but never approves or hides anything
  ([ADR 0014](0014-ai-is-optional-and-only-advises.md)).
- A child can ask for something with a "wish" in the app. A wish is only a note in the inbox.

## Consequences

- Nothing unseen reaches a child unless a parent chose to trust that channel.
- The inbox is ongoing work for the parents. Trusted channels, bulk approve and AI warnings are there to keep it small.
- A trusted channel can still post something unwanted. Hiding is quick, but it is after the fact.

## Alternatives

Approve whole channels only: simpler, but one bad upload gets through. Let AI approve: a wrong call has no parent in
the loop.

## Where it lives

`server/app/curation/approval.py`, `server/app/curation/blocklist.py`, inbox in the admin page.
