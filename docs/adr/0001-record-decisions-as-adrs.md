# 0001. Record decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

This project has two parts (a server and an Android TV app) and a long idea list (`docs/ideas.md`). Without a record,
the reasons behind early choices get lost, and later sessions re-argue them.

## Decision

Each design decision gets one short file in `docs/adr/`, in the format WhatsOn uses: Context, Decision, Consequences,
Alternatives, Where it lives. Status is `Proposed`, `Accepted`, `Rejected`, `Deprecated` or `Superseded by ADR NNNN`.
An accepted ADR's reasoning is never rewritten; a new ADR replaces it.

The first batch (0002 to 0029) was written before any code, from the idea list. The owner accepted them on 2026-11-22,
and "Where it lives" names the planned location.

## Consequences

- Decisions are findable and have a stated cost.
- Writing ADRs before code means some will be wrong. Expect a few to be superseded in the first milestone.

## Alternatives

One big design doc: harder to change one decision without touching the rest. No record: see Context.

## Where it lives

`docs/adr/`, indexed in `docs/adr/README.md`.
