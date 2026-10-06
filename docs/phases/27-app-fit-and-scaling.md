# Phase 27 — Apps Fit Their Window

## Objective

Applications and web pages did not fit the space Hyprland gave them: content
was cut off on the right (option b) and the laptop felt cramped (option a).
Vesktop was the reported case. Zooming apps was explicitly rejected; apps
must fit the provided display.

## Status

Implemented and applied. Vesktop and Spotify were verified visually at their
new widths. Lunar Client/Minecraft with the XWayland filter change was not
observed.

## Diagnosis

1. **Cramped laptop.** `eDP-1` (1920×1200) at scale 1.5 gave only a
   1280×800 logical desktop, so web pages fell back to compact layouts.
2. **Clipped Electron apps.** A QuickCSS probe in Vesktop showed its page
   viewport was at least 940 px while Hyprland tiled the window at 790 px.
   Vesktop has a 940 px minimum window width: below it the app keeps
   drawing at 940 px and Hyprland clips the overflow. No CSS can adapt the
   layout because the page never sees a narrower viewport. Spotify
   behaves the same way with an 800 px minimum: its layout was identical at
   762 and 800 px, only clipped at 762.
3. **Pixelated XWayland apps.** XWayland windows on a fractionally scaled
   monitor are upscaled; `xwayland:use_nearest_neighbor` was `true`.

Hyprland's Lua API and `hyprctl clients` do not expose a client's minimum
size, so it cannot be detected automatically.

## Changes

- `modules/monitors.lua` and DMS `~/.config/hypr/dms/outputs.lua`:
  `eDP-1` scale 1.5 → 1.25 (logical 1536×960); `HDMI-A-2` moved from
  `1280x0` to `1536x0` so it stays adjacent. DMS reads its saved display
  layout back from `outputs.lua`, so both files were changed together.
- `modules/monitors.lua`: `xwayland.use_nearest_neighbor = false`.
- New `modules/app_min_sizes.lua`, loaded from `hyprland.lua`: a table of
  measured minimum widths (`vesktop` 940, `spotify` 800). After windows open,
  close, or move between workspaces, and when the config loads, any tiled
  window narrower than its minimum is widened by moving its split, using
  `hl.dsp.window.resize` with an exact width. It only does so when the
  minimum plus 360 px per other window in the same row fit on the monitor;
  otherwise the layout is left alone.
- The cursor sync from Phase 26 regenerated images for the new scale
  (36, 45, 72 px).

An intermediate attempt — responsive QuickCSS media queries for Vesktop —
was removed once the minimum-width cause was found; Vesktop's
`quickCss.css` was restored to its original empty state.

## Files changed

Repository:

- `hypr/.config/hypr/modules/monitors.lua`
- `hypr/.config/hypr/modules/app_min_sizes.lua` (new)
- `hypr/.config/hypr/hyprland.lua` (`require("modules.app_min_sizes")`)
- `docs/phases/27-app-fit-and-scaling.md`

Machine (not versioned):

- `~/.config/hypr/dms/outputs.lua` (scale and position).
- Active copies of `hyprland.lua`, `modules/monitors.lua`, and
  `modules/app_min_sizes.lua`.
- Backups: `~/.config/hypr/dms/outputs.lua.before-phase27`,
  `~/.config/hypr/modules/monitors.lua.before-phase27`,
  `~/.config/hypr/hyprland.lua.before-phase27`.

## Validation

- `hyprctl reload`: `ok`; `configerrors` empty after each change. Live
  monitors: `eDP-1` 0,0 scale 1.25; `HDMI-A-2` 1536,0 scale 1.
- Vesktop: tiled at 790 px it rendered a ≥940 px viewport (clipped). After
  the module it is 940 px (Kitty 640) and the screenshot shows the full UI:
  complete search field, row actions, and window controls.
- Event path: with a temporary third window in the row the minimum cannot
  fit; the first version of the module collapsed Vesktop to 35 px. The row
  guard was added. Retest: with three windows the layout is left as Hyprland
  computed it, and after closing the temporary window Vesktop is 940 px again.
- Spotify: screenshots at 762 px (clipped) and 800 px (complete). Reset to
  762 px and reloaded; the module restored 800 px. Brave, the neighbor, is
  716 px and adapts normally.
- `cursor_sync.py --check`: all consumers agree. Tests: theme 22 OK, cursor
  14 OK, layout 1803 pass; `build-theme.py --check` and
  `dms-overlay.sh --check` pass; DMS active.

During the investigation, a resize probe without a window selector resized
the active Spotify window to 960 px; the split was restored right after.
Restarting Vesktop with a remote-debugging port was refused by the agent
permission system and not used; the measurements came from QuickCSS probes
and screenshots instead.

Not validated: Minecraft/Lunar Client appearance with the XWayland filter,
and behavior after a new login.

## Known limitations

- Minimums are measured per app and must be added to `MIN_WIDTH` by hand;
  Hyprland does not report them. To measure one, tile the app narrower,
  then widen it until the content stops being clipped without reflowing.
- If the row cannot fit an app's minimum (for example three windows across
  `HDMI-A-2`), the app is still clipped; only fewer windows in the row or a
  wider monitor solves that.
- Widening uses the dwindle split, so it may reverse a manual narrower
  resize of that app on the next window open/close.
- Only widths are handled; minimum heights were not measured.

## Rollback

Remove `require("modules.app_min_sizes")` from `hyprland.lua`, restore the
three `.before-phase27` backups, and run `hyprctl reload` and
`scripts/cursor_sync.py --apply`.
