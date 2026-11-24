# 0035. Importing what the boys already have approved

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The boys already have channels and videos approved in YouTube Kids ("Approved content only"). Starting over by hand
is slow. YouTube Kids lets a parent see and edit the approved list in its settings, but we found no way to export it:
no export button, and Google's help pages don't say whether Google Takeout includes it. Takeout does export a
YouTube account's subscriptions, playlists and history.

## Decision

An **Import** screen (Add › Import) with three ways in, all ending in the same review step:

1. **Paste a list.** Any mix of channel, video and playlist links, one per line or comma separated, for example
   copied from the YouTube Kids approved list on a computer, or typed while looking at it.
2. **Google Takeout files.** Upload the `subscriptions.csv`, playlist CSVs and the watch history from a Takeout
   export of a YouTube account. Useful if the boys watched under a supervised YouTube account or a parent's account.
   (The watch history was added on 2026-11-23, see the revision below.)
3. **A YouTube playlist.** A parent can build one playlist of everything approved, on the phone, then paste its link.

**Review step.** The server reads every link (with channel pictures, ADR 0030) and shows the list: channels with
their picture and video count, single videos with thumbnails. For each the parent picks:

- who it is for (default: both boys),
- for channels: **subscribe** (new uploads only, or the latest N) or **just mark approved** (nothing downloads
  until a parent adds videos),
- or **skip**.

Everything imported is **approved**: this is the parent confirming a decision already made in YouTube Kids. Imported
channels are marked **trusted** only if the parent ticks it. The import runs as a job (ADR 0032) with pacing
(ADR 0004), so a long list does not hammer YouTube.

### Revised 2026-11-23: what a Takeout of the boys' accounts holds, and the watch history

The owner ran a Takeout of both boys' supervised accounts. It has **no list of YouTube Kids approvals**. Each boy's folder
holds `subscriptions.csv`, `watch-history.html` and `search-history.html`. A YouTube Kids watch history lists one
entry per watch with only the video link: no title and no channel.

So the Takeout input takes the watch history too:

- **A file box per boy** (and one for a shared account), several files at once. What comes out of a boy's files is
  offered for him by default; a link in both boys' files is offered for both.
- **Only the videos watched most come in:** those one boy watched 3 times or more (the parent can pick 2, 5 or 10),
  at most 1,500 in one import, most watched first. Each is looked up like any other link, paced, so about a thousand
  videos take two to three hours (about 8 seconds a link when tried). Adverts and the search history are left out.
- **Grouped by channel in review.** After the lookups every channel the watched videos came from gets a row (not
  looked up again), most watched first, with its videos folded under it. Per channel the parent picks **Subscribe**
  (follow the channel and bring in the watched videos), **Just the videos** (the default: download those, leave the
  channel alone) or **Skip**. One setting leaves out every such channel under 10, 25, 50 or 100 watches.

**It lives through a restart** (2026-11-23, after a deploy cut the first real import off at 125 of 1,081 links):
a read that is stopped leaves the import as it is, and at startup the server carries on with the links still
waiting.

Trade-off: watching something three times is not the same as a parent approving it. The review step is where the
parent decides; nothing comes in without it.

## Consequences

- The move from YouTube Kids is a few minutes of review instead of re-approving by hand.
- The YouTube Kids list itself still has to be copied by hand until an export is found.
- A big import downloads a lot; pacing spreads it over days, which the review step says up front.

## Alternatives

Scraping the YouTube Kids website while signed in: against its terms, fragile, and needs the parent's Google login
in our server. Skipping import: hours of re-approving.

## Where it lives

`server/app/downloads/importer.py`, `server/app/api/extras.py` (`/import/...`), `server/app/static/admin/app.js`
(Add › Import), `server/migrations/0006_import_watch_history.sql`.
