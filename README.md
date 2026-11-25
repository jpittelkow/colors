# colors

A self-hosted kids' video app for one household. A server downloads, holds and curates the videos a parent
approves; an Android TV app plays only those, with time limits the server keeps. Parents run it from a web page on
their phone or computer.

It was built for two small children who were used to YouTube Kids, so the TV app looks and behaves much like it:
profiles with characters, rows of big thumbnails, a side menu, a timer, spoken "all done" lines. Nothing reaches
the TV that a parent did not allow.

## What it does

**Parents' page** (web, phone or desktop)

- Search YouTube, add a video, a playlist or a whole channel by link; subscribe to channels with rules (new only,
  latest N, length, Shorts, live, title filters, pacing, retention).
- Approve or hide what comes in; blocked words; per-profile access to channels and single videos.
- Plex: allow a show, movie or collection, streamed through the server.
- Limits per child: daily allowance, longest sitting, closed hours, a one-off limit, +minutes, "last one" (exactly
  one more video), end now, unlock.
- Time-fit: when a limit runs, only videos that finish in the time left are offered.
- SponsorBlock skips and your own skips, counted in time-fit.
- Even out the volume: every video measured once, the TV turns it up or down and softens loud moments.
- Not watched lately: channels a boy can watch but hasn't started in 30 days, with why and one-tap fixes (pause downloads, rest, take away, delete, keep).
- Watch history and weekly reports per child; downloads and background jobs with live progress.
- Optional AI picks through OpenRouter (no child's name or birthday is ever sent).
- Home Assistant API with its own key (status, lock everything, extra time, vacation mode).

**TV app** (Android TV / Google TV, Android 11+)

- Pair with a six-digit code or a QR code; pick a profile.
- Home rows, Channels, Recently watched, Recommended, New; a channel's videos.
- Player with resume, skipped parts, Start over, autoplay up to the parent's count.
- Timer, "pick one more", time's up, break and closed-hours screens, with recorded spoken lines and a QR code that
  opens that child's page for a grown-up.

## Run the server

Docker (any host):

```bash
docker build -t kidtube .
docker run -d --name kidtube -p 8460:8460 \
  -v /path/to/data:/data -v /path/to/videos:/library \
  -e KIDTUBE_ADMIN_PASSWORD=change-me kidtube
```

Then open `http://<host>:8460/admin/`. Unraid template and update script: [docs/runbooks/deploy.md](docs/runbooks/deploy.md).

| Variable | Meaning |
|---|---|
| `KIDTUBE_DATA_DIR` | Database, cookies file, your own characters (`/data` in the image) |
| `KIDTUBE_LIBRARY_DIR` | Downloaded videos (`/library` in the image) |
| `KIDTUBE_ADMIN_PASSWORD` | Sets the parents' password on first start only |
| `KIDTUBE_PLEX_URL`, `KIDTUBE_PLEX_TOKEN` | Optional; the page's Plex screen can set them instead |
| `KIDTUBE_FFMPEG_DIR` | Folder holding ffmpeg, only when it is not on the PATH |
| `KIDTUBE_POT_URL` | A [bgutil PO token helper](https://github.com/Brainicism/bgutil-ytdlp-pot-provider), e.g. `http://<host>:4416`. Recommended: without it YouTube soon asks a busy server to "confirm you're not a bot" |
| `TZ` | Time zone for the day rollover and closed hours |

### Develop

Needs Python 3.12, ffmpeg, and Node or Deno (yt-dlp needs a JavaScript runtime for YouTube).

```bash
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python run_dev.py        # http://localhost:8455/admin/
.venv/Scripts/python -m pytest -q
```

Data and downloaded videos go in `server/dev-data/`, which is not in git.

## Build the TV app

See [tv/README.md](tv/README.md). In short: JDK 17, `cd tv && ./gradlew assembleRelease`, then `adb install` on each TV.
Put your server's address in `tv/local.properties` (`colors.server=http://<host>:8460`) or type it on the TV.

## How it is decided

Every design decision is an ADR in [docs/adr](docs/adr/README.md): what was chosen, why, and what was ruled out.
The idea list is [docs/ideas.md](docs/ideas.md).

## Notes

- Home network use. The parents' page has a password; the TV app pairs per device. There is no HTTPS of its own:
  put it behind your own reverse proxy if it leaves the house.
- "kidtube" is the internal name (container, database, settings); "colors" is what children and parents see.
- Downloading from YouTube is your responsibility under YouTube's terms where you live.
- The built-in characters and icon are original. Add your own characters in `<data>/characters/` (ADR 0036) and
  your own TV icon through `colors.res` in `tv/local.properties`, outside this repository.

## License

MIT, see [LICENSE](LICENSE). The Fredoka font is under the SIL Open Font License (`tv/app/FONT-LICENSE-Fredoka.txt`).
