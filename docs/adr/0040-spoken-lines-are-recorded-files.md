# 0040. The TV's spoken lines are recorded files in the kids app's voice

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The TV app says a few lines out loud: "pick one more", "all done for today", the break and good-night screens. The
first build used Android's text-to-speech. On the kids' TVs that voice is flat and robotic, it differs from TV to TV,
and some TVs have no voice data installed at all. The boys already know a narrator from the kids app: ElevenLabs v4,
voice Maisie, made by that app's own generator. The owner: use the audio generator from the kids app for our generated
audio. Maisie is the voice now; Matilda was retired.

## Decision

Every spoken line is an MP3 made ahead of time and bundled in the APK as `res/raw/voice_<id>.mp3`.

- `tv/voice/lines.json` is the list. Each line has `say` (sent to the voice, with a delivery tag like `[warmly]`)
  and `show` (the same words without the tag). The screen prints `show`, so what is written matches what is heard.
- `tv/voice/generate.mjs` follows the kids app's `tools/sounds/generate.mjs`. It runs wherever the OpenRouter key
  already is (for us, a container on the home server), so the key never travels; only the audio comes back. It makes
  three takes of each line.
- `tv/voice/prepare.py` trims the silence and levels each take the way the kids app does (RMS 0.13, peaks under
  0.9, mono 44.1 kHz). Take 1 ships unless a `line=take` pick says otherwise. `tv/voice/voice.json` records what
  shipped.
- **The lines never contain a child's name** (ADR 0034). The old text-to-speech lines said "Great watching, Sam";
  the recorded ones say "Great watching!". The name stays on screen, under the avatar and in the hint.
- The app plays a line with `MediaPlayer`. A new line stops the one still playing.

| Line | When |
| --- | --- |
| `one_more` | the last pick of the day (ADR 0011) |
| `all_done` | the day's time is used up |
| `break` | a session ran out and a break is due |
| `good_night` | closed hours |
| `stopped` | a parent stopped watching or locked the profile |

## Consequences

- One voice everywhere, the same on every TV, and the boys already know it from the kids app.
- A new line, or new words, means running the generator and rebuilding the app. That is fine for a handful of fixed
  lines. Anything that has to say something different each time would need a live voice, which this ADR does not
  allow.
- The APK grows by about 200 KB.
- Swapping a take is a one-line re-run: `python tv/voice/prepare.py <takes folder> good_night=2`.
