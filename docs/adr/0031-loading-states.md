# 0031. Loading states: skeletons and a spinner, never bare text

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Several screens wait on YouTube for seconds: search, reading a pasted link, reading a channel before subscribing.
Today they show the words "Reading the channel…" on an empty page, which looks broken on a phone.

## Decision

- The design system gains two components:
  - **Skeleton**: grey shapes in the layout of what is coming (thumbnail rows, a channel header), with a slow
    shimmer. Used when the shape of the answer is known.
  - **Spinner**: a small round spinner in `brand`, used inside buttons while their action runs and for short waits.
- Every wait longer than about 300 ms shows one of them, plus one line that says what is happening in plain words
  ("Looking up Digger Dan on YouTube"). Waits over 10 seconds add "This can take a while for big channels".
- Buttons that start an action show the spinner in place of their label and can't be pressed twice.
- Both respect `prefers-reduced-motion`: the shimmer and spin stop and the shapes stay.

## Consequences

- Waiting looks intentional and the page keeps its layout, so nothing jumps when results arrive.
- Two more components to keep in the design system and the page.

## Alternatives

A full-screen overlay: blocks the page and hides progress. Text only: what we have, and it reads as broken.

## Where it lives

Design system `components/Skeleton`, `components/Spinner`, `bundle.css`; `server/app/static/admin/`.
