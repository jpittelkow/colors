# colors, the TV app

The Android TV app children use (ADR 0015, 0016, 0017). Kotlin, Jetpack Compose, Media3. It draws the screens the
server sends and never decides what is visible. Look: `docs/design/reference.md`.

## Build

```bash
cd tv
./gradlew.bat assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

Toolchain: JDK 17, Gradle 9.8.2, AGP 9.4.1, compileSdk 37.

If Gradle fails with "Unable to establish loopback connection", the temp folder is too long for Java's local
sockets. Run it with a short one:

```bash
export JAVA_TOOL_OPTIONS="-Djdk.net.unixdomain.tmpdir=C:\\tmp\\gradle-sock" TEMP='C:\tmp' TMP='C:\tmp'
```

The Compose release is pinned to 2026.09.00: newer ones need the android-37.1 platform.

## Your settings

`tv/local.properties` (git-ignored, next to the SDK path) holds this household's choices:

```properties
colors.server=http://192.168.1.10:8460   # the server a fresh TV tries first; leave out to type it on the TV
colors.res=/path/to/your/res             # optional: resources that replace the built-in ones (icon, banner)
```

Release builds are signed with the key named in `tv/keystore.properties` (git-ignored: `storeFile`,
`storePassword`, `keyAlias`, `keyPassword`). Keep that key safe: a TV only accepts an update signed with the same key.

## Build types

| Type | Package | Use |
|---|---|---|
| debug | `app.colors.tv.dev` | development; installs beside the real app |
| staging | `app.colors.tv.staging` | the release build (R8) against the dev server through `adb reverse tcp:8455 tcp:8455` |
| release | `app.colors.tv` | the TVs |

## Install

```bash
adb -s <tv-ip>:5555 install -r app/build/outputs/apk/release/app-release.apk
adb -s <tv-ip>:5555 shell cmd package compile -m speed-profile -f app.colors.tv   # smooth from the first run
```

A debug build can be pointed at another server with
`adb shell am start -n app.colors.tv.dev/app.colors.tv.MainActivity --es server http://<host>:8460` (release builds
ignore that; there the address is typed on the TV).

The app then shows a six-digit code and a QR code. Pair it on the parents' page: Kids › TVs › Pair a new TV.

## What is in it (milestone 1 and the time screens of 2)

- Finding the server (typed address if it doesn't answer), pairing with code and QR (ADR 0018, 0039).
- Who's watching, the home rows with the reference look, a channel's videos.
- The player: resume, skipped parts, heartbeats, stop when the server says, autoplay up to the parent's count,
  the up-next rows (the controls scroll), the screen between videos (ADR 0044).
- Timer, "one more", time's up and closed hours, with a QR code for a parent and the line spoken aloud.

Not yet: the grown-ups passcode, "together", search, a channel page header with its picture, the control socket
(ADR 0019), self-update (ADR 0015), finding the server by mDNS.

Supported from Android 11 (API 30).

The Fredoka font files in `app/src/main/res/font/` come from the @fontsource/fredoka package (SIL Open Font
License, `app/FONT-LICENSE-Fredoka.txt`), converted with `scripts/woff_to_ttf.py`.
