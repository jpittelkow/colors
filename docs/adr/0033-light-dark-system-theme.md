# 0033. Light, dark or system theme, chosen in the page

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The parents' page follows the phone's light or dark setting. The owner wants to choose. The design system already
defines every colour for both themes.

## Decision

- A theme setting with three choices: **System** (default), **Light**, **Dark**, in More › Appearance and as a quick
  toggle in the top bar's menu.
- The choice sets `data-theme="light"` or `data-theme="dark"` on the page root; System removes it. `tokens.css`
  defines the dark values under both `@media (prefers-color-scheme: dark)` (guarded by
  `:root:not([data-theme="light"])`) and `:root[data-theme="dark"]`, so an explicit choice wins either way.
- The choice is kept in the browser (local storage), per device, because one parent may want dark on the phone and
  light on the computer. It is applied before the page draws, so there is no flash of the wrong theme.
- The design system documents the same three-state rule so the TV app can follow it later.

## Consequences

- A parent picks once per device.
- The setting doesn't follow a parent to another device. Acceptable; it is a viewing preference, not data.

## Alternatives

A server-side setting shared by all devices: forces one choice on every screen. Dark only: ignores daytime use.

## Where it lives

`server/app/static/admin/tokens.css`, `index.html` (early theme script), `app.js` (Appearance); design system
README.
