# 0036. Profile avatars: a set of our own illustrated characters

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Profiles show a letter today. The boys can't read (ADR 0016), so on the TV the "Who's watching?" picker must work by
picture. The owner wants avatars in line with what YouTube allows now. YouTube Kids profiles use illustrated characters
that a parent or the child picks (Google's help pages show characters such as a ninja and a piece of toast); we found
no option to use a photo.

## Decision

- Each profile has an **avatar**: one of a fixed set of illustrated characters, plus a background colour from the
  design system's identity colours.
- The set is **our own artwork** (ADR 0016), not YouTube's characters: about 24 simple, round, friendly characters
  (animals, vehicles, food, space), drawn as SVG in the flat style of the mockup thumbnails, so they stay sharp on a
  TV and weigh almost nothing.
- **No photos** of the children: nothing to store or leak, and it matches YouTube Kids.
- The parent picks in the page (Profiles › the profile › Avatar), from a grid. The TV app will later let a child
  change their own avatar from the same set, as YouTube Kids does.
- Each child profile gets a different character by default so the boys can tell themselves apart from the start.
- The avatar is stored as an id (`fox`, `rocket`) and a colour token. The SVGs ship with the server and are served
  at `/avatars/<id>.svg` to both the page and the TV app.

## Amendment, 2026-11-23

The boys already have characters they know from YouTube Kids, and the owner wanted those back. That artwork is not
ours, so it is not in this repository (it went public the same day):

- **A household's own characters** live in the server's data folder, `<data>/characters/<id>.svg`. They are listed
  beside the built-in set, chosen the same way, and served at the same `/avatars/<id>.svg`. Whoever runs the server
  is responsible for what they put there.
- A parent can also **upload a picture** for a profile (PNG, JPEG, WebP or GIF, up to 3 MB). It is stored as
  `custom:<id>.<ext>` and served at `/avatars/custom/<id>.<ext>`. Still no photos of the children: that part stands.
- The circle colours are the same bright colours in light and dark, as on the TV picker.

## Consequences

- The boys can find themselves by picture on day one.
- A fixed set to draw and maintain; adding a character is one SVG file, in the repo or in the data folder.

## Alternatives

Photos: personal data about children for little gain. Letters only: fails for children who can't read. Copying
YouTube Kids' characters: their artwork, ruled out by ADR 0016.

## Where it lives

`server/app/static/avatars/`, `profiles.avatar` (already in the schema), `server/app/static/admin/app.js`,
design system `components/Avatar`.
