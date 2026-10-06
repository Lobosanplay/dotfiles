# Phase 26 — Unified Cursor Size and Theme

## Objective

The cursor was a different size in Minecraft (Lunar Client) than in other
applications. Find the cause and add a repository-owned mechanism so the
cursor has one theme and one size in every application.

## Status

Implemented and applied on this machine. Automated checks pass. The visual
result in a restarted Lunar Client and after a new login was not observed by
the agent and remains for the user to confirm.

## Diagnosis

- DMS stores `Frieren-Winter` at 36 px. Hyprland, the systemd user
  environment, GSettings, Flatpak overrides, and Lunar Client's own process
  environment all already reported theme `Frieren-Winter` and size 36. The
  preference was not the problem.
- Lunar Client 1.8.9 runs under XWayland (`xwayland=true`) on `eDP-1`
  (scale 1.5). Brave, Vesktop, Kitty, and Nautilus are native Wayland.
- Parsing the installed theme files showed the two formats ship different
  image sizes:

  | Format | Location | Image sizes before |
  | --- | --- | --- |
  | Xcursor | `~/.icons/Frieren-Winter/cursors` | 24, 32 (original art is 32 only) |
  | Hyprcursor | `~/.local/share/icons/Frieren-Winter/hyprcursors` | 24, 36 |

- Neither libXcursor nor Hyprcursor rescales to the requested size; both use
  the nearest image. Wayland apps that let the compositor draw the cursor got
  the 36 px Hyprcursor image; XWayland apps such as Minecraft got the 32 px
  Xcursor image, and on `eDP-1` Hyprland then upscaled that X surface ×1.5.
  Client-drawn Wayland cursors could land on yet another image. This is the
  size difference.
- Secondary finding: `~/.Xresources` contained the cursor values, but they
  were never loaded into XWayland (`xrdb -query` was empty).

## Design

- DMS remains the only owner of the cursor preference; no new token or
  setting was added. `scripts/cursor_sync.py` derives everything from
  `cursorSettings` in DMS `settings.json`.
- For a user-installed theme, the original art is snapshotted once to
  `~/.local/share/dotfiles/cursor-sources/<theme>/` and both formats are
  regenerated from it at exactly the preferred size and its physical size on
  each live monitor scale, plus 2× (36, 54, 72 here). No smaller sizes are
  generated so clients asking for a default such as 24 still get 36. Pixels
  are resampled in premultiplied alpha with Lanczos; hotspots and animation
  delays are preserved. Each format directory is built aside and swapped in.
- System themes under `/usr/share/icons` are never modified.
- The same run aligns GSettings, `~/.icons/default/index.theme`,
  `~/.Xresources` plus `xrdb -merge`, and the Flatpak override environment,
  and reports (but does not touch) a stale DMS `cursor.lua`.
- `dotfiles-cursor-sync.path` re-runs the sync when DMS saves its settings;
  `dotfiles-cursor-sync.service` also runs at login (`hyprland-session.target`).
  A stamp in `~/.local/state/dotfiles/cursor-sync.json` makes unchanged runs a
  ~0.1 s no-op.
- Dependency: Pillow (`python3-pillow`, already installed from Fedora) for
  resampling; it is imported only when images must be generated.

## Files changed

Repository:

- `scripts/cursor_sync.py` (new)
- `tests/cursor/test_cursor_sync.py` (new, 14 tests)
- `systemd/.config/systemd/user/dotfiles-cursor-sync.service` (new)
- `systemd/.config/systemd/user/dotfiles-cursor-sync.path` (new)
- `docs/architecture/cursor.md`
- `docs/phases/26-unified-cursor.md`

Machine (not versioned):

- Snapshot of the original art: `~/.local/share/dotfiles/cursor-sources/Frieren-Winter/`
  (`cursors/` = Xcursor 24/32, `hyprcursor/` = previous Hyprcursor 24/36).
- Regenerated `~/.icons/Frieren-Winter/cursors` and
  `~/.local/share/icons/Frieren-Winter/hyprcursors` (36/54/72), plus the
  `.dotfiles-cursor-generated` marker.
- `~/.Xresources` unchanged in content; merged into XWayland.
- The two units copied to `~/.config/systemd/user/` and enabled.
- The existing backup `~/.icons/Frieren-Winter.before-size24-20261005` and
  `Frieren-Winter.tar.gz` were left untouched.

## Validation

- `python3 -B scripts/cursor_sync.py --check` before applying: reported the
  theme-image and Xresources drift (exit 1). After `--apply`: “all cursor
  consumers agree” (exit 0).
- Parsed regenerated Xcursor files: `left_ptr`, `xterm`, `watch` contain
  exactly 36, 54, and 72 px images. A Hyprcursor archive was unpacked and its
  54 px frame inspected visually: art intact, hotspot at the arrow tip.
- `hyprctl setcursor Frieren-Winter 36`: `ok`; no cursor errors in the
  Hyprland log; `hyprctl configerrors` empty.
- `xrdb -query` now returns `Xcursor.size: 36` and `Xcursor.theme: Frieren-Winter`.
- Units: service ran successfully under systemd; opening `settings.json` for
  append without writing triggered the path unit (file hash unchanged).
  `systemd-analyze --user verify` reported nothing.
- Tests: cursor 14 OK, theme 22 OK, layout 1803 pass;
  `build-theme.py --check` and `dms-overlay.sh --check` pass; DMS active.

Not validated: the cursor inside a restarted Lunar Client/Minecraft, and the
behavior after a new login. `hyprcursor-util` could not be used to verify the
archives because its extract mode needs `xcur2png`, which is not installed.

## Known limitations

- Original art is 32 px; 54 and 72 px are upscaled, so they are as soft as
  Hyprland's previous on-the-fly upscaling, not sharper.
- Running applications keep cursor images they already loaded; Lunar Client
  must be restarted.
- The unit and stamp paths assume the repository at
  `~/Documents/projects/dotfiles`, like the other units (see Phase 25).
- Only cursor theme and size are unified. GTK/Qt widget themes and the
  per-monitor application scaling of XWayland apps (blurry ×1.5 upscale on
  `eDP-1`) are out of scope.

## Rollback

Disable `dotfiles-cursor-sync.path` and `.service`, copy the snapshot's
`cursors/` and `hyprcursor/hyprcursors/` back into the two theme directories,
remove the marker, and run `hyprctl setcursor Frieren-Winter 36`.
