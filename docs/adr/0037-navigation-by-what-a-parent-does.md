# 0037. The parents' page is organised by what a parent does, and has a desktop layout

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The parents' page grew one feature at a time and ended up organised by how the server works: Add, Inbox, Library,
Kids, More. The owner, after using it: adding from Plex is in a weird spot, the Add page is empty and could be combined
with the library, and it is not clear what the inbox does. The audit (`docs/ui-audit-2026-11-23.md`) found adding
in four places, two look-alike search boxes with different reach, an Inbox that never says what it is, a More
screen with twelve unrelated rows, and the boys split across two tabs. On a computer the page is the phone column
in the middle of an empty screen; the owner asked for a proper desktop version too.

## Decision

**Four tabs, named for what a parent does.**

1. **Library**: everything the boys can watch, and the only search box. A search looks in three places and shows
   them as sections: in your library, in Plex, on YouTube. A pasted link is read as a video, playlist or channel.
   An **Add** button lists every other way in: browse Plex, import from YouTube Kids, ideas from the AI. The
   library itself can be seen as channels or as videos, for everyone or for one boy. A channel only shows here
   once it has something approved or a subscription.
2. **Approve** (was Inbox): the videos waiting for a parent's yes, and it says so at the top. Grouped by channel,
   with worded buttons (Approve, Not for them), "Approve all" per channel and "Always approve this channel".
   Failed and stopped downloads are not shown here; they belong to Downloads.
3. **Kids**: each boy's card, and behind it one page with everything about him: watching now, time, limits, his
   week, his picture and name. Vacation mode, TVs and adding a profile live on this tab.
4. **Settings** (was More), in four groups: Server (downloads, jobs, library size), Safety (blocked words,
   skipping), Connections (Plex, AI, Home Assistant), This page (appearance, password, sign out).

**Flows that change with it.**

- Search results carry a "For: Sam, Alex" choice that is remembered on the device; **+** adds for those boys
  and says where the video went.
- Subscribe shows the channel, who it is for, the approve-without-asking switch and the button first; the rules
  are folded under "More options".
- Plex splits: connecting is in Settings › Connections; browsing and allowing is under Add.
- Channel and video screens have a title, their main actions at the top, and plain words ("Hide from the boys",
  "Parts to skip").
- One selected-chip style that cannot be read the wrong way round (filled in the brand colour with a tick); row
  actions are worded buttons; every screen leaves room at the bottom so the activity pill never covers a button.

**A desktop layout, same page and same code.** From 900 px wide the tabs become a sidebar on the left with the
wordmark above and the activity pill at its foot, and the content uses the width: grids of 4 to 6 across in the
library and in search, the boys' cards side by side, settings groups in columns, the download history as a
table. Approve becomes two panes: the list, and the selected video with a preview player and its buttons; the
arrow keys move through the list, A approves, X says no. Forms (subscribe, limits, a profile) stay a narrow
centred column at any width. Phones keep the bottom bar and one column.

## Consequences

- One place to look for anything, one place to add anything, and a screen that says what it wants from you.
- Old addresses (`#inbox`, `#more`, `#downloads` under More) change. Nothing outside the page links to them.
- More CSS: a second layout to keep working. It is the same markup, so a screen cannot exist on one and not the
  other.
- A search now asks YouTube and Plex at the same time as the library; the library and Plex answers show first and
  YouTube fills in when it arrives.

## Alternatives

Keep five tabs and only rename Inbox: leaves adding in four places. A separate desktop page: two things to build
and keep in step. A "Home" dashboard tab: one more screen between a parent and the library; the Approve badge and
the activity pill already say what needs attention.

## Where it lives

`server/app/static/admin/app.js`, `app.css`, `index.html`; `server/app/api/admin.py` (items: profile filter,
paging, deciding several at once), `server/app/api/manage.py` (channels: counts and who sees them). Supersedes the
tab list in ADR 0025; amends ADR 0009 (the inbox is now "Approve").

## Revision 2026-11-23: Downloads and Jobs in the nav, the household in Settings

The owner, after a day of use, and the second navigation audit (`docs/nav-audit-2026-11-23.md`):

- **Six places in the nav:** Library, Approve, Kids, **Downloads**, **Jobs**, Settings. Downloads and Jobs were
  two taps deep under Settings › Server although they are the pages you check while something is going on. Each
  shows a count when something needs a look (failed downloads; jobs whose last run failed), like Approve. On a
  phone the labels drop to 11 px below 440 px wide so six fit; if a seventh place is ever wanted, Downloads and
  Jobs share one "Activity" place instead.
- **The household moves to Settings:** Vacation mode, TVs and Profiles are the first group there. Kids is only
  the boys' cards (right now: watching, time, +10 min, end now) and each boy's own page, which keeps "Picture and
  name".
- **Library:** the search box and Add sit in one row in the top bar; on a phone the wordmark has its own line
  above.
- **Settings is four groups:** Household, Safety (one row: blocked words and parts to skip, one page), Connections,
  This page. The Server group is gone: **Library size** is the last section of Downloads, with its own Save.
- **A boy's page holds his week and his history** (ADR 0021 revision); the separate "This week" screen is gone and
  `#reports/<id>` opens his page. Each card on Kids ends in a worded button, "Sam's history, week and limits →",
  because the small "›" on his name was easy to miss.
