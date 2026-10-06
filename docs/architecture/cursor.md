# Cursor configuration architecture

## Source of truth and flow

DMS owns the user's cursor preference in
`~/.config/DankMaterialShell/settings.json` (`cursorSettings.theme` and
`cursorSettings.size`). When those settings change, DMS writes the generated
Lua module `~/.config/hypr/dms/cursor.lua`, applies the cursor immediately with
`hyprctl setcursor`, and requests a Hyprland configuration reload. The module
exports both `HYPRCURSOR_*` and `XCURSOR_*` values so native Wayland and
XWayland consumers can use the selected theme and size.

The repository's `hyprland.lua` sets size 36 as a fallback before loading
`modules.dms`. That module optionally loads `dms.cursor`, allowing persisted
DMS preferences to take precedence. On a fresh machine without generated DMS
state, the fallback remains available. Do not edit `dms/cursor.lua` directly;
DMS regenerates it from its settings.

DMS currently stores `Frieren-Winter` at size 36. The Xcursor assets are
installed under `~/.icons/Frieren-Winter`; a matching Hyprcursor theme is
installed under `~/.local/share/icons/Frieren-Winter`. Both theme
installations are machine-local and are not versioned.

## Uniform size across applications

Neither libXcursor nor Hyprcursor rescales a theme to the requested size: each
picks the nearest image size the theme ships. A theme whose formats ship
different sizes is therefore drawn at different sizes depending on the
client path:

| Client path | Format read | Examples |
| --- | --- | --- |
| Compositor-drawn (cursor-shape protocol) | Hyprcursor | GTK4, Chromium/Electron, Kitty |
| Client-drawn Wayland | Xcursor | GTK3 and older toolkits |
| XWayland | Xcursor (via the X server) | Minecraft/Lunar Client (LWJGL), Java, X11 apps |

`scripts/cursor_sync.py` keeps one size everywhere. It reads the DMS
preference (DMS stays the only owner) and:

1. For a user-installed theme, snapshots the original art once to
   `~/.local/share/dotfiles/cursor-sources/<theme>/` and regenerates both
   formats from it with exactly the preferred size and its physical size on
   each monitor scale (plus 2×). For 36 px on scales 1 and 1.5 that is 36, 54,
   and 72 px. No smaller size is generated, so a client that requests a
   default such as 24 resolves to the preferred size. The original theme
   directory gets a `.dotfiles-cursor-generated` marker. System themes under
   `/usr/share/icons` are never modified.
2. Points the remaining consumers at the same theme and size: GSettings,
   `~/.icons/default/index.theme`, `~/.Xresources` (merged into XWayland with
   `xrdb`), and the Flatpak user override environment.
3. Reloads Hyprland's cursor with `hyprctl setcursor` after regenerating.

`--check` reports drift and exits 1; `--apply` is idempotent and only
resamples when the theme, size, monitor scales, or source change (state in
`~/.local/state/dotfiles/cursor-sync.json`). The user units
`dotfiles-cursor-sync.service` (run at login) and `dotfiles-cursor-sync.path`
(run when DMS saves `settings.json`) apply it automatically, so changing the
cursor in DMS settings is the only step needed. Applications that are already
running keep the cursor images they loaded; restart XWayland apps to pick up
regenerated images.

To return to the original theme files, copy
`~/.local/share/dotfiles/cursor-sources/<theme>/cursors` back into the theme
directory (and `hyprcursor/` into the Hyprcursor theme), remove the marker,
and disable the two units.

At Hyprland startup, the existing startup hook calls
`dbus-update-activation-environment --systemd --all` so the compositor's
environment is available to user services and DBus-activated applications.
GTK may also use the desktop cursor setting stored through GSettings/dconf;
DMS maintains Xcursor resources for XWayland. These layers are separate from
the DMS preference and may affect application-specific sizing.

## Wayland, XWayland, and scaling

The current Brave window is native Wayland (`xwayland=false`) on `eDP-1` at
scale 1.5. ChatGPT is XWayland (`xwayland=true`) on `HDMI-A-2` at scale 1.0.
This means the applications use different cursor paths and monitor scales.
Their perceived cursor dimensions can differ even when they share a theme and
logical size. There is no per-application override in the project.

The custom `Frieren-Winter` theme is installed under `~/.icons`, which is
machine-local and is not included in the repository. A fresh setup must install
that theme separately or select an available theme in DMS.

## Legacy Xcursor and Flatpak fallback

The user-local `~/.icons/default/index.theme` inherits `Frieren-Winter` so
legacy Xcursor clients that request the default theme resolve to the selected
cursor. Flatpak user overrides grant read-only access to `~/.icons` and export
`XCURSOR_THEME=Frieren-Winter`, `XCURSOR_SIZE=36`, and a search path containing
the user theme directory. These are machine-local runtime settings; the theme
and size values are kept in sync by `scripts/cursor_sync.py`, while the
filesystem grant and `XCURSOR_PATH` remain manual. Newly launched applications
pick up the settings; already-running XWayland clients may need to be
restarted.

Application backend selection remains per application. Use native Wayland when
the app supports it and behaves correctly; keep XWayland available for legacy
or incompatible apps. Cursor consistency does not require forcing every
application onto the same backend.

## Validation boundary

The DMS preference and generated module are persistent files. A normal config
reload validates Lua/config loading, but does not prove post-login behavior;
verify the cursor after a new login when available. Cursor appearance should
also be checked in native Wayland and XWayland applications on both monitor
scales before changing scale or adding application-specific workarounds.
