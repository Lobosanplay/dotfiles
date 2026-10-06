# Phase 28 — Autostart and hyprland-guiutils Warning

## Objective

1. Vesktop and Spotify did not start with the session; they should start
   automatically on workspace 2.
2. Hyprland shows a startup warning that `hyprland-guiutils` is not
   installed; find how to install it or how to silence the warning.

## Status

Autostart implemented and applied. Placement was verified live with the
startup logic run on config load; a real login was not observed. The
`hyprland-guiutils` package was not installed by the agent (requires
`sudo`); the install path was verified with a dry run.

## Findings

- `~/.config/autostart/` has entries for both apps (Flatpak
  `com.spotify.Client` and `dev.vencord.Vesktop`), but nothing runs them:
  `hyprland-session.target` does not pull in `xdg-desktop-autostart.target`,
  which stays `inactive (dead)`. The repository had no autostart of its own.
- Hyprland exec rules (`hl.exec_cmd(cmd, rules)`) match the spawned PID,
  which does not survive the Flatpak sandbox reliably. A class window rule
  would also move windows the user opens later.
- Spotify sets its class after the window maps; Vesktop maps a splash
  window with class `vesktop` before its main window.
- `hl.dsp.window.move({ workspace, follow = false, window })` moves a window
  without moving focus (checked with a temporary kitty window).
- `hyprland-guiutils` 0.2.2 is in the `lionheartp/Hyprland` COPR, the same
  repository the installed `hyprland-0.56.2-3.fc44` comes from. A dry run
  installs only it and `hyprtoolkit` 0.6.0 (about 2 MiB), with no removals.
  Hyprland also has `misc:disable_hyprland_guiutils_check` to disable the
  warning.

## Changes

- New `hypr/.config/hypr/modules/autostart.lua`, loaded from
  `hyprland.lua` after `modules.app_min_sizes`. On `hyprland.start` it runs
  `flatpak run` for each app and arms its class. For 120 s, on
  `window.open` and `window.class`, every mapped window of an armed class
  (compared in lowercase) is moved once to its workspace with
  `follow = false`. After the timer, nothing is moved.
- No change for the guiutils warning; the decision is left to the user
  (install the package, or set the option).

## Files changed

Repository:

- `hypr/.config/hypr/modules/autostart.lua` (new)
- `hypr/.config/hypr/hyprland.lua` (`require("modules.autostart")`)
- `docs/phases/28-autostart-and-guiutils.md`

Machine (not versioned):

- Active copies of `hyprland.lua` and `modules/autostart.lua`.
- Backup: `~/.config/hypr/hyprland.lua.before-phase28`.
- `~/.config/autostart/*.desktop` left untouched.

## Validation

- `hyprctl reload`: `ok`; `hyprctl configerrors` empty.
- Live test: a temporary copy of the module ran the startup body on load
  instead of on `hyprland.start`. First version (move only the first
  window per class): Spotify landed on workspace 2, Vesktop stayed on 1
  (the splash consumed the move). Current version: both on workspace 2,
  active workspace stayed 1. The real module was restored afterwards
  (`cmp` identical) and the config has no errors.
- An earlier attempt restored the file before the windows mapped; Hyprland
  auto-reloads on config file changes, which reset the Lua state, so
  nothing was moved. Not a problem at login, where no file changes occur.
- `workspace-graph.json` unchanged (`{"1":{},"2":{}}`).
- Not validated: behavior on a real login.

## Known limitations

- A Vesktop or Spotify window opened by hand within 120 s of login is also
  sent to workspace 2.
- If either app takes more than 120 s to show its window, it stays on the
  workspace where it opened.
- If XDG autostart is ever enabled in the session, the apps would start
  twice; then the `~/.config/autostart` entries should be removed.

## Rollback

Remove `require("modules.autostart")` from `hyprland.lua` (or restore
`~/.config/hypr/hyprland.lua.before-phase28`) and delete
`modules/autostart.lua`.
