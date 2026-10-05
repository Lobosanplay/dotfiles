# Cursor configuration architecture

## Source of truth and flow

DMS owns the user's cursor preference in
`~/.config/DankMaterialShell/settings.json` (`cursorSettings.theme` and
`cursorSettings.size`). When those settings change, DMS writes the generated
Lua module `~/.config/hypr/dms/cursor.lua`, applies the cursor immediately with
`hyprctl setcursor`, and requests a Hyprland configuration reload. The module
exports both `HYPRCURSOR_*` and `XCURSOR_*` values so native Wayland and
XWayland consumers can use the selected theme and size.

The repository's `hyprland.lua` sets size 24 as a fallback before loading
`modules.dms`. That module optionally loads `dms.cursor`, allowing persisted
DMS preferences to take precedence. On a fresh machine without generated DMS
state, the fallback remains available. Do not edit `dms/cursor.lua` directly;
DMS regenerates it from its settings.

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

## Validation boundary

The DMS preference and generated module are persistent files. A normal config
reload validates Lua/config loading, but does not prove post-login behavior;
verify the cursor after a new login when available. Cursor appearance should
also be checked in native Wayland and XWayland applications on both monitor
scales before changing scale or adding application-specific workarounds.
