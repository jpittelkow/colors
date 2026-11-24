# 0010. Profiles: one per child, content assigned per profile

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Two boys of different ages share the TVs. What suits one may not suit the other, and each should have his own history,
favorites and time allowance.

## Decision

- A **profile** per child: name, avatar, birthday, and its own history, favorites, playlists, home rows and limits.
- Approved content is **assigned** to profiles. A container or item can be for one profile or several. Assigning a
  container covers its items unless an item says otherwise.
- The TV app opens on a "Who's watching?" picker. Switching profile is free; there is no PIN between children. This is
  about the right content and separate time, not security between brothers.
- A **together** mode covers both boys on one TV: only content assigned to both is shown, and time is taken from both
  allowances.
- A **guest** profile exists for visiting friends, with its own small allowance and a parent-chosen set of content.
- A **grown-up** profile sits behind the parent gate ([ADR 0018](0018-pairing-parent-gate-and-kiosk.md)).
- Optional age bands: content tagged with an age range becomes available automatically when a birthday passes, if the
  parent turned that on for the profile.

## Consequences

- A child can pick his brother's or the guest profile to get different content or more time. **Accepted by the owner on
  2026-11-22** ("don't worry about profile hopping"); the boys are 2 and 4. Revisit with
  [ADR 0027](0027-keeping-kids-inside-the-app.md).
- Assignment is one more step when approving. Defaults ("both boys") keep it to one tap.

## Alternatives

One shared kids' library: no per-child time or history. A PIN per child from the start: friction for small children
who cannot type one.

## Where it lives

`server/app/profiles/`, picker in `tv/` (`ui/profiles/`).
