# 0015. A native Android TV app: Kotlin, Compose for TV and Media3

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The kid-facing client runs on Android TV devices (Chromecast with Google TV first). It has to feel like a real app
with a remote, play video smoothly on weak hardware, and be hard to leave.

## Decision

- A native app in Kotlin with **Jetpack Compose for TV** for the interface and **Media3 (ExoPlayer)** for playback.
- Remote-first: every screen works with the d-pad, select and back. No touch assumptions.
- Minimum Android version is set from the oldest TV in the house, checked before the first build.
- Images load through one cache (Coil). Scrub previews use a sprite sheet the server makes.
- Distribution is a signed APK, sideloaded. The app checks the server for a newer APK and offers the update behind the
  parent gate. The server hosts the APK; there is no store.
- The app holds no library data and no secrets beyond its device token
  ([ADR 0017](0017-the-tv-app-is-a-thin-client.md), [ADR 0018](0018-pairing-parent-gate-and-kiosk.md)).
- The APK is signed with one release key. The key and its password are kept outside the repository, with a backup
  copy, because a lost key means uninstalling and re-pairing the app on every TV.
- Built from the same repository as the server (`tv/`), with the API types generated from the server's OpenAPI file.

## Consequences

- Best playback and focus handling on the target devices. Keeping the boys inside the app is done outside it
  ([ADR 0027](0027-keeping-kids-inside-the-app.md)).
- Android only. A tablet or iPad client later is new work, though an Android tablet can reuse most of it.
- Sideloading and self-update need "install unknown apps" allowed for the app on each TV.
- A second language and toolchain (Kotlin, Gradle) beside Python.

## Alternatives

A web app in a WebView or a TV browser: one codebase, but poor focus handling, weaker video on these devices, and easy
to escape. Flutter or React Native: TV support is thinner than native. A Plex or Jellyfin skin: cannot enforce the
rules.

## Where it lives

`tv/` (`app/src/main/java/.../ui`, `.../player`, `.../net`).
