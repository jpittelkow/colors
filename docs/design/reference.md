# TV app look: the reference

Measured on 2026-11-23 from a kids profile ("Sam") in the YouTube app on the a Chromecast with Google TV,
captured over adb at 1920×1080 (ADR 0016). This file is the source of truth for the look. The screenshots
themselves are not in the repository, because they show what the boys watch (ADR 0021).

All sizes are pixels on a 1920×1080 screen. Font is Roboto unless it says "playful", which is the rounded display
face YouTube uses for names and titles; we use Fredoka for that.

## Colours

| What | Value |
|---|---|
| Side panel | `#1a0059` |
| Sky (top part of the screen) | `#0f0f0f` |
| Hills band | `#7f00bf` |
| Ground (bottom part) | `#2c2580` |
| Clouds | `#42414a` |
| Focus plate, selected pill, light text | `#f1f1f1` |
| Text on a focus plate | `#0f0f0f` |
| Row label, row not focused | `#9f9ea6` |
| Watched line, pause button | `#ff0033` |
| Channel card not focused | white at about 35%, `#f1f1f1` outline 3 px |
| Dimmed screen behind "Who's watching?" | sky `#050505`, ground `#00001f` |
| Dark pills (exit, gear) | `#1a1a36` |
| Player pills | `#2b2b27` |
| Player bar | played `#f1f1f1`, loaded `#6a6968`, rest `#5b5a58` |
| Channel page background | `#362b7a` over the channel's banner |

## Home

- **Side panel, closed:** 156 wide. Profile picture 54 across, centred at x 78, y 102; the name under it, 24 px,
  centred, y 157. Home icon at y 231. Two more icons pinned to the bottom at y 915 and y 993. All icons white, 36 px.
- **Side panel, open** (focus moved left): 510 wide. Each entry is a row 78 tall: icon at x 78, label at x 123,
  30 px medium. The selected entry is a `#f1f1f1` pill, 444×78 at x 33, radius 16, with dark indigo text.
  Order: profile (top), Home, then at the bottom the two utility entries.
- **Scenery:** the sky is the top 600 px. A band of purple hills with small trees sits from about y 600 to y 720.
  Below it the ground colour runs to the bottom. A few clouds in the sky, a few yellow dots near the hills. The
  scenery does not move when rows scroll.
- **Logo:** top right, x 1678 to 1815, y 78 to 127.
- **Rows:** exactly two are on screen: the focused row in the sky, the next row on the ground.
  - Row label: x 240, 34 px bold capitals, centred on y 150. `#f1f1f1` for the focused row, `#9f9ea6` for the other.
    The second row's label is centred on y 780.
  - Moving down slides the next row up into the sky position. The last row leaves the ground empty.
- **Video card:** thumbnail 528×297, radius 16. First card at x 240; cards are 600 apart (72 gap). Thumbnail top at
  y 195 in the focused row and y 825 in the next row.
  - Title: 34 px bold, 2 lines, line height 48, starting 16 under the thumbnail. No channel name, no age, no views.
  - Length: bottom right of the thumbnail, 12 in from the edges, 24 px medium white on a dark rounded patch.
  - Watched line: 6 px along the bottom edge of the thumbnail, red for the part watched.
  - **Focused:** a `#f1f1f1` plate, radius 28, reaching 12 px beyond the thumbnail on the top and sides and down
    past the title (552×426 at x 228, y 183). The title turns `#0f0f0f`. Nothing grows or moves.
- **Channel card:** same footprint as a video card with its title (528×402). A circular picture 246 across, the
  channel name in the playful face, 44 px, and one line under it, 30 px: "Channel", or a tick and "Subscribed".
  Not focused: translucent with a white outline. Focused: the same `#f1f1f1` plate, dark text.
- **Scrolling along a row:** after the first card, the side panel slides away and the row uses the full width. The
  focused card sits in the second position (x 840) and the card before it shows cut off on the left.
- **Rows seen, in order:** Recommended, Shared, Approved for you, Top channels, Watch it again.

## Who's watching?

- Opens when the profile entry in the side panel is focused, over a dimmed home screen.
- Title in the playful face, 60 px, centred on y 205.
- Profile circles 296 across, 360 apart, tops at y 312. Name under each, 36 px, y 657.
- **Focused:** a 6 px `#f1f1f1` ring around the circle with a small gap, the name in white, a second line under
  the name (24 px, grey), and a round gear button (72 across) at y 792.
- One pill button low on the screen, centred, y 888, 72 tall, `#1a1a36`, 24 px bold.

## Channel page

- **Top:** the channel's banner fills the screen, fading into indigo on the left and bottom. A round back arrow top
  left (x 96, y 63). At x 96, y 464: the channel picture (72 across), its name (36 px bold) and one grey line
  under it. Then up to three lines about the channel (30 px, line height 42, about 830 wide) and a `#f1f1f1` pill
  button (72 tall). The first row of videos shows cut off at the bottom, from y 918.
- **Scrolled:** the banner stays behind a `#362b7a` wash. Header: picture 72 across at x 96, y 72, name in the
  playful face, 56 px. Videos in a grid of 3: columns at x 96, 660 and 1224; rows 534 apart from y 228. Cards and
  focus plate as on the home screen.

## Player

- Nothing shows while a video plays. Pressing select shows the controls over a dark wash.
- Title top left in the playful face, 56 px bold, up to 2 lines, x 96, from y 100. Channel name under it, 24 px.
- Time played at x 96 and total length right-aligned to x 1824, both 22 px, y 678.
- Bar from x 96 to x 1824, 8 px tall, y 726, rounded.
- Row of controls centred on y 816: a "Back" pill at the left (162×72, arrow and word), a round red play/pause
  button in the middle (96 across, white ring), a pill at the right with two icons.
- Under the controls, a row of what plays next: thumbnails 528×297, 600 apart, from x 96, y 897, cut off by the
  bottom of the screen. Moving down focuses them.

## What the reference does not have

No search, no categories row, no likes, no comments, no clock. Our own screens (pairing, the timer, "one more",
time's up, closed hours, the parent gate) are designed in this style: same panel, same scenery, same plate, same
pills (ADR 0016).
