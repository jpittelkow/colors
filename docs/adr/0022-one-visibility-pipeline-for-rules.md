# 0022. One visibility pipeline; extra rules are plug-in steps

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The idea list has many rules about what a child may see or play right now: approval, profile, schedules, time-fit,
repeat limits, category budgets, learn-first, calm-only evenings, together mode. Written separately they would
disagree and be hard to explain.

## Decision

- Every list sent to the TV and every play request goes through **one pipeline** of steps, in a fixed order:
  1. **Approved** ([ADR 0009](0009-nothing-is-shown-unless-approved.md)).
  2. **Assigned** to the profile, or to both in together mode ([ADR 0010](0010-profiles-and-who-can-see-what.md)).
  3. **Open**: schedule, lockout and mode ([ADR 0011](0011-the-server-keeps-the-clock.md)).
  4. **Optional rules**, each a small step that can remove items or mark them locked with a reason:
     - repeat limit (plays of one item per day);
     - category budget (minutes per tag per day);
     - learn-first (fun items stay locked until a learning item is finished today);
     - calm-only hours (by energy tag);
     - rested containers and dated rows ([ADR 0013](0013-parents-build-the-home-screen.md)).
  5. **Time-fit**, always last ([ADR 0012](0012-only-show-what-finishes-in-time.md)).
- A step either **hides** an item or shows it **locked** with a reason. The boys cannot read, so the reason is a
  picture and a spoken line ([ADR 0016](0016-match-the-youtube-kids-look.md)). Which of the two is a setting of the
  rule.
- **Together mode** applies the optional rules of both profiles; the stricter one wins.
- **The grown-up profile** passes through steps 1 and 2 only, with its own assignments.
- **Parent overrides** (a pushed video in [ADR 0019](0019-control-the-app-over-its-own-connection.md), a movie-night
  pass in [ADR 0028](0028-long-items-parts-and-movie-night.md)) are the only ways past steps 3 to 5, and both are
  logged.
- If the optional rules leave nothing playable while time remains, they are waived for the session
  ([ADR 0012](0012-only-show-what-finishes-in-time.md)).
- Each optional rule is off by default, switched on per profile, and has its own small settings.
- Rewards that add time (quiz after a learning video, earned minutes from Home Assistant) do not live here. They add to
  the allowance ledger in [ADR 0011](0011-the-server-keeps-the-clock.md).
- The admin page has a **"why can't he see this?"** check: pick a profile and an item, and it lists each step and its
  answer.
- A guard test fails the build if a TV route returns items without going through the pipeline
  ([ADR 0029](0029-migrations-tests-and-guards.md)).

## Consequences

- One place to reason about, test and explain every rule. New rules are one step each.
- The fixed order is a choice: for example, a rested channel is hidden even from "Continue watching".
- The pipeline runs on every list. It must be fast; it works on ids and cached facts.

## Alternatives

Rules scattered through the API handlers: quick to start, impossible to explain later. A general rule language for
parents: powerful, and far too much for one household.

## Where it lives

`server/app/rules/` (`pipeline.py`, `steps/`), check tool in the admin page.
