# 0008. Plex and Jellyfin: allow-listed, streamed in place

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The household already has kids' shows and movies in Plex. Bringing them into the same app must not expose the rest of
the library.

## Decision

- Nothing from Plex or Jellyfin appears by default. A parent allows content by **collection, label, or single show or
  movie**. A content-rating filter (for example TV-Y to TV-G) can be offered as a shortcut, but only inside what was
  allowed.
- The server keeps the Plex or Jellyfin token. The TV app never holds it. The app receives a stream URL from our
  server, which proxies the stream.
- **Direct play only, to start with.** Many Plex files are HEVC, 4K or DTS, which the TVs may not play. When an item
  is allowed, the server checks its video and audio format against what the TVs play. An item that passes is proxied
  as a plain file. An item that fails is **not shown**, and the admin page lists it with the reason and two ways out:
  make a compatible copy in Plex (an optimized version), or wait for transcoding support.
- Proxying a media-server transcode session is a later ADR. It is not part of the first Plex milestone.
- Watch progress is written back to a chosen Plex or Jellyfin user per profile, and read from it, so "continue
  watching" agrees in both places.
- Both servers can be connected at once, unlike WhatsOn's one-server rule, because here they are just two sources.

## Consequences

- No copies of files, and the existing libraries stay as they are.
- This part of the app stops working when Plex or Jellyfin is down.
- Some allowed movies will not appear until a compatible copy exists. How many is unknown until the kids' collection
  is checked.
- Proxying hides the token at the cost of traffic through our server. Both run on the same host, so the cost is small.
- A movie tagged wrongly in Plex can slip through a label or rating rule. Explicit collections are the safe default.

## Alternatives

A Plex managed user with restrictions and the Plex app: no time-fit, no shared look, and the Plex app is a way out.
Redirect the app to a direct Plex URL: puts a Plex token on the TV.

## Where it lives

`server/app/sources/plex.py`, `server/app/sources/jellyfin.py`, allow rules in `server/app/curation/allow.py`.
