# Kids' own YouTube — idea list (2026-11-22)

Working list to go through with the owner. Nothing is built. Shape agreed so far: one server (profiles, downloads, hosting, curation) plus an Android TV app styled like the main YouTube app, playing only local videos.

Tags show where an idea comes from: **[W]** WhatsOn, **[Y]** an earlier download manager, **[K]** kidplex, **[G]** a TV overlay app, **[new]**.

## A. Finding and adding content (server)
- A1. Search YouTube from the admin page (yt-dlp search, no API key) with thumbnails, length, channel, upload date. [new]
- A2. Paste any URL (video, playlist, channel, Short) and it works out what it is. [Y]
- A3. Channel subscribe with rules: everything, only new uploads, last N, only videos matching a title filter, skip Shorts, skip live streams, min/max length. [Y]
- A4. Preview before approving: watch the video in the admin page straight from YouTube before it downloads. [new]
- A5. Phone share target: share a video from the YouTube app on your phone to the server ("Add for the boys"). [new]
- A6. Browser bookmarklet or extension button: "Add this video / channel". [new]
- A7. Import from an existing YouTube account: watch history, liked videos, or a YouTube Kids approved list. [new]
- A8. Starter packs: one-click sets of known-good channels by age and topic. [new]
- A9. One search bar across everything: local library, YouTube, and Plex kids' shows. [W]
- A10. Per-video approval inside a subscribed channel: new uploads wait in an inbox until you tick them, or auto-approve per trusted channel. [new]

## B. Downloading and library (server)
- B1. Job queue with progress, retry, logs, and a dashboard. [Y]
- B2. Scheduled channel checks with per-channel intervals, download delay and concurrency limits. [Y]
- B3. Cookies file support and automatic yt-dlp updates, with an alert when downloads start failing. [Y]
- B4. Quality cap per profile or channel (720p for toddlers' cartoons, 1080p for the rest). [new]
- B5. SponsorBlock: cut sponsor reads, intros, "like and subscribe" segments at download time or skip them at playback. [new]
- B6. Subtitles downloaded and available in the player. [new]
- B7. Storage rules: keep last N per channel, delete watched after X days, never delete favorites, total size cap. [new]
- B8. Duplicate detection and re-download protection. [Y]
- B9. Folder layout that Plex/Jellyfin can also read, so the library works even without the custom app. [Y]
- B10. Health page: disk used, failed downloads, channels that went quiet or got deleted. [Y]
- B11. Archive protection: a video removed from YouTube stays in the library, marked as "gone upstream". [new]
- B12. iGPU transcode to a TV-friendly format once at download so playback never transcodes. [Y]

## C. Profiles and parental controls (server)
- C1. A profile per boy with avatar, age band, and their own library view, history and playlists. [K]
- C2. Content assigned per profile: a channel can be for Sam, Alex, or both. [new]
- C3. Daily screen-time allowance per profile, with separate weekday and weekend limits. [K]
- C4. Session timer and lockout: "20 minutes, then the app closes for an hour". [K]
- C5. Bedtime and school-morning schedules when the app won't open. [K]
- C6. "Last one": the player finishes the current video and stops, triggered from your phone. [new]
- C7. Remote pause and "time's up" message on the TV from your phone. [W]
- C8. Earned time: chores or reading logged in Home Assistant add minutes. [new]
- C9. Parent PIN area inside the TV app (settings, switching to a grown-up profile). [K]
- C10. Repeat limiter: cap how many times the same video can be played per day. [new]
- C11. Category budgets: unlimited "learning", 30 minutes of "junk". [new]
- C12. Vacation and sick-day modes that loosen the limits, tied to `input_boolean.vacation_mode`. [new]

## D. Curating what they see (server)
- D1. You build the home screen: ordered rows ("New this week", "Trains", "Science", "Dad's picks"). [W — sections UI]
- D2. Pinned and featured videos at the top, with an expiry date. [new]
- D3. Recommendation rules you control: "after a cartoon, suggest a learning video", weightings per row. [new]
- D4. "Up next" only from approved content, with a cap on autoplay chain length (or off). [new]
- D5. Rotation: hide a channel for a few weeks, bring it back later so the library feels fresh. [new]
- D6. Seasonal and themed rows that switch on by date (Halloween, Christmas, summer). [new]
- D7. Playlists per boy, shared playlists, and "bedtime wind-down" playlists that end with a stop. [new]
- D8. Scheduled programming: a "Saturday morning cartoons" block that appears only then. [W — guide idea]
- D9. A fake "live channel" that plays a looping schedule of approved videos, like TV. [W]
- D10. Mix in non-YouTube content: home videos, Plex kids' shows, audiobooks/music videos. [W]
- D11. Kid requests: a "wish" button in the app (or voice), which lands in your approval inbox. [new]
- D12. Hide a video or channel instantly from your phone when you see something you dislike. [new]

## E. AI features (server)
- E1. Auto-tagging on download: topic, age fit, energy level (calm vs. hyper), educational vs. entertainment. [W — AI model dropdown]
- E2. Transcript-based screening: flag language, scary themes, toy-unboxing or ad-heavy videos for your review before approval. [new]
- E3. Plain-English search for you: "calm videos about volcanoes under 10 minutes". [W — AI search]
- E4. Channel report card before subscribing: what the channel is like across its last 50 uploads. [new]
- E5. Suggest new channels based on what they actually finish watching, for you to approve. [W — AI suggestions]
- E6. Weekly digest for you: what each boy watched, new favorites, anything flagged. [W — "Catch me up"]
- E7. Auto-built playlists: "a 30-minute mix of space videos for Sam". [new]
- E8. Clean titles and thumbnails: rewrite clickbait titles, pick a calmer frame as the thumbnail. [new]
- E9. Voice search in the TV app limited to the local library. [new]
- E10. Model choice in settings, local or cloud, with AI fully optional. [W]

## F. The TV app (looks like YouTube)
- F1. YouTube-style layout: left rail, thumbnail rows, channel pages, red progress bars, duration badges. [new]
- F2. "Who's watching?" profile picker on launch. [K]
- F3. Subscriptions, History, Library and "Watch later" tabs that work on the local library. [new]
- F4. Search with the on-screen keyboard and voice, local results only. [W]
- F5. Resume where you left off, watched markers, "Continue watching" row. [W — Up next]
- F6. Fake like button and a favorites list that feed your curation stats. [new]
- F7. Shorts-style vertical feed built from approved short clips, with a hard count limit. [new]
- F8. No comments, no ads, no external links, nothing that leaves the app. [new]
- F9. Gentle time-up flow: countdown, a wind-down screen, then lock. [K]
- F10. Offline cache on the device for car trips or tablets. [new]
- F11. Phone/tablet version of the same app (Android first, PWA for iPad). [K]
- F12. Set as the home screen on the kids' TV, or a kiosk mode that blocks leaving the app. [G — Projectivy/launcher work]
- F13. In-app updates from a private release feed. [kidsapp — updates from GitHub Releases]
- F14. A grown-up profile behind the PIN showing your own downloaded channels. [new]

## G. Remote control and the house
- G1. Now-playing bar for each TV in the admin page: what's on, who, time left today, pause and stop. [W]
- G2. Push a video or playlist to a TV from your phone ("play this for them now"). [W — tune to TV]
- G3. Full phone remote for the kids' TV. [W — remote]
- G4. Home Assistant entities: watching/not, minutes used today, current video; services for pause, lock, add time. [G]
- G5. Doorbell and "dinner's ready" pop-ups over the video. [G]
- G6. Automations: pause when the doorbell rings, lock at bedtime scene, lights dim for the wind-down playlist. [G]
- G7. Block real YouTube on kid devices (adb disable, DNS rules on UniFi) so the lookalike is the only one. [TCL debloat]
- G8. Uptime Kuma monitor and Telegram alerts for failed downloads or a full disk. [existing infra]

## H. Insight for you
- H1. Watch history per boy with totals by channel, topic and day. [new]
- H2. "Finished vs. skipped" stats to see what they actually like. [new]
- H3. Rewatch leaderboard. [new]
- H4. Trend alerts: one channel taking over, screen time creeping up. [new]

## I. Project decisions to make
- I1. Build the server fresh, or fork an earlier download manager (it already has channels, jobs, logs, settings, scheduler)?
- I2. Own video hosting, or lean on Plex/Jellyfin for streaming and only build the curation layer?
- I3. Which devices first: which TVs do the boys use, and is a tablet in scope?
- I4. Private only, or open source later like WhatsOn (affects naming, logo, no bundled YouTube branding)?
- I5. How close to YouTube's look: same layout and feel with its own name/icon (recommended), or closer?
- I6. First milestone: suggested = server with A1–A3, B1–B3, C1, D1 + TV app with F1, F2, F5.

## J. Round 2 (2026-11-22) — the owner's decisions and added ideas
**Decided:** all of A–H are in. TV app should match the YouTube Kids app as closely as possible. Plex and Jellyfin content comes into the same app (all-in-one). Admin sets a time limit and the app only shows videos that will finish inside it.

### Time-fit (the owner's idea, expanded)
- J1. Library shrinks as time runs out: only videos whose length fits the remaining time are shown.
- J2. Counts remaining length for part-watched videos (a 40-min video with 5 min left fits a 10-min window).
- J3. Grace setting: allow a video to overrun by up to N minutes.
- J4. "Fill the time" button for the parent: auto-build a playlist that ends on the minute.
- J5. Final pick screen: "one more — choose from these three" when little time is left.
- J6. Long content split into parts by chapter so movies/long videos fit sessions ("continue tomorrow").
- J7. Movie-night pass: a one-off override that allows one long title.
- J8. Per-session limit and daily limit both, shared across every TV and tablet.
- J9. Kid-visible timer (YouTube Kids-style) or hidden — per profile.
- J10. "Watching together" mode: both boys on one TV = content both are allowed, time taken from both.

### Plex / Jellyfin in the same app
- J11. Shows appear as "channels", episodes as videos, same cards as YouTube content.
- J12. Allow-list by Plex collection, label or rating; nothing appears by default.
- J13. Stream straight from Plex/Jellyfin (no copies); watched state syncs back.
- J14. Movies get their own category tab.
- J15. Live row from the existing Dispatcharr Kids profile.
- J16. Music tab: kids' playlists and music videos via Music Assistant.
- J17. Audio-only stories/audiobooks mode with the screen off (bedtime, car).

### YouTube Kids look
- J18. Category bar with icons (Shows, Music, Learning, Explore), mapped from the AI tags.
- J19. Big rounded cards, avatar profile picker, intro splash, button sounds.
- J20. Parent gate like theirs (sum question or passcode).
- J21. Animated "time's up" lock screen.

### Other new ideas
- J22. Learn-first rule: a learning video unlocks fun ones.
- J23. AI quiz after an educational video for bonus minutes.
- J24. Family channel: home videos from your phone, video messages from grandparents.
- J25. Calm-only evenings using the energy tag; volume cap.
- J26. Break prompts between videos ("stand up and stretch").
- J27. Guest profile for friends visiting.
- J28. Travel mode: sync a chosen set to a tablet.
- J29. Pick on a tablet, play on the TV (kidplex-style).
- J30. Keyword block list across titles and transcripts.
- J31. HA dashboard card with an "everything off" button.
- J32. Age-up: content bands widen automatically on birthdays.
