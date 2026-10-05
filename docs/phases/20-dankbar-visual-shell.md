# Phase 20 — DankBar / Visual Shell Integration

## Status

Implemented as a DMS native custom theme and a small DankBar settings profile.
The profile was applied to the current user's DMS settings with a backup.
Static validation passed; visual runtime validation was unavailable because
DMS IPC and the Hyprland control socket were not accessible in this session.

## Context

Phase 20 adapts the 43PR visual language to the DankBar already provided by
DMS 1.6.2. It does not add another bar, `PanelWindow`, Quickshell shell,
workspace manager, or DMS QML override. The requested Phase 16 audit document
`docs/phases/16-43pr-audit.md` is absent from this checkout; Phase 17–19
records and the installed DMS source were used instead.

## DMS inspection and integration choice

The installed UI is `/usr/share/quickshell/dms`, with DankBar widgets,
three-section layout, a native workspace switcher, center clock, system tray,
battery, notification, and control-center widgets. DMS exposes individual
bar configuration in `~/.config/DankMaterialShell/settings.json` and supports
custom theme JSON through `customThemeFile`. The repository's
`scripts/dms-overlay.sh --check` passed against installed DMS 1.6.2 and its
existing overview overrides. Since the bar is configurable without replacing
QML, Phase 20 does not add files to `dms/overrides` or alter the overlay
mechanism.

The active DMS settings originally used a blue stock theme and placed music,
clock, and weather in the center, system tray and battery at the left, and
system-monitor widgets at the right. The profile now uses:

| Group | Native DMS widgets |
| --- | --- |
| Left | Launcher, Hyprland workspace switcher |
| Center | Clock |
| Right | System tray, battery, notifications, control center |

This centers the clock through DMS's existing center section. It removes the
music/weather and CPU/memory/temperature widgets from the bar to reduce visual
noise. Audio, network, Bluetooth, and related controls remain available in
DMS's existing control center. No unsupported status widget was added.

## 43PR visual language adapted

- Compact three-group composition with clock centered geometrically.
- Restrained spacing, a softly rounded surface, and a 0.9 panel alpha.
- A quieter, single cohesive bar surface rather than individual widget cards.
- Workspace indicators use DMS's native Hyprland data and show the active
  workspace index. Active and occupied colors use the theme's primary and
  secondary roles; urgent and inactive states retain DMS's state handling.
- No linear wheel navigation is introduced. The profile disables bar scroll
  interactions and leaves the existing WorkspaceGraph keybindings untouched.

The profile uses 4 logical units of inter-widget spacing, 2 units of inner
padding, 5 units of widget padding, and 0.9 font/icon scale factors. DMS
calculates bar geometry from the output's device scale and its own bar-height
settings. The existing user corner radius is retained. These values are a
starting proportion, not a pixel-for-pixel reproduction of 43PR.

## Theme integration

`scripts/build-theme.py` now also renders
`dms/themes/graphite-blue/theme.json` from the shared preset through
`themes/templates/dms-theme.json.tmpl`. The template maps DMS's primary,
secondary, surface, text, outline, and semantic-state fields onto the existing
Graphite Blue token roles. The generated file is a DMS custom theme, not a
second authored palette.

The profile selects that theme using DMS's native `currentThemeName=custom`
and `customThemeFile` settings. This selects static Graphite Blue for DMS as a
whole, because DMS applies its theme globally; DMS does not expose a separate
DankBar-only palette. Phase 19's `dynamic-colors.json` is not connected to
DMS in this phase. DMS's own wallpaper/Matugen system is not invoked or
replaced by the profile.

## Typography and iconography

DMS already bundles Inter Variable and Material Symbols Rounded, matching the
Phase 18 UI family and icon provider. The compact profile sets DMS's native
bar scale factors and does not install fonts. Native widgets own their
individual icon ligature names; DMS has no settings API to map them to the
project's semantic alias table. No glyphs were copied into QML.

## Workspace indicators

DankBar's native Hyprland workspace switcher reads compositor state. The
profile enables compact index labels and focused/occupied color states; it
does not read or write `workspace-graph.json`, alter graph connections, or
change navigation bindings. DMS's bar uses direct workspace activation on
indicator clicks, while graph navigation remains the responsibility of the
existing overview and `SUPER+ALT` arrow bindings. Bar wheel handling is
disabled to avoid imposing a linear sequence on the non-linear graph.

## Applying and reverting

The profile lives at `dms/presets/dankbar-43pr.json`. Apply it with:

```bash
python3 -B scripts/build-theme.py --write
# Stop DMS before editing its settings file, then start it again afterward.
python3 -B scripts/apply_dankbar_preset.py --apply
```

The applier should run while DMS is stopped: a running shell can save its
in-memory settings over an external edit. It copies the generated theme to
`~/.config/DankMaterialShell/themes/dotfiles-graphite-blue/theme.json` and
changes only the selected theme, workspace-indicator preferences, and the
`default` bar config in DMS settings. It preserves other keys and bar
properties. Before its first change it creates
`settings.json.before-phase20` (or a numbered variant without overwriting an
existing backup). Revert the settings by restoring that backup and remove the
`dotfiles-graphite-blue` custom-theme directory if no longer used. The
repository theme and preset remain available for reapplication.

## Multi-monitor and performance

The profile targets DMS's existing default bar assignment (`all`) and does
not hardcode output dimensions. DMS calculates bar thickness and geometry
with the scale of each output; per-output visual rendering still needs a live
check on eDP-1 at scale 1.5 and HDMI-A-2 at scale 1. No timers, polling,
external processes, animations, blur effects, or per-frame work were added.

## DMS update safety

No DMS implementation file was copied or overridden, so the Phase 15 overlay
upstream fingerprint mechanism remains unchanged. `scripts/dms-overlay.sh --check`
reported that the current workspace-overview overrides match DMS
1.6.2. The profile and generated custom theme use DMS's installed native
settings/theme interfaces; they do not depend on the overlay path.

## Validation

- `python3 -B scripts/build-theme.py --write` generated the existing Hyprland
  theme module and the DMS custom theme.
- `python3 -B scripts/build-theme.py --check`: passed.
- `python3 -B -m unittest discover -s tests/theme -v`: 17 tests passed,
  including DMS role mapping, profile application to a temporary settings
  file, preservation of unrelated preferences, backup creation, idempotence,
  and refusing to replace another custom theme.
- Python bytecode syntax compilation: passed.
- `python3 -m json.tool` validated the generated DMS theme and profile.
- `scripts/dms-overlay.sh --check`: passed; installed DMS and override base
  both report version 1.6.2.
- `python3 -B scripts/apply_dankbar_preset.py --apply` applied the preset to
  the personal DMS settings and created
  `~/.config/DankMaterialShell/settings.json.before-phase20`.
- `python3 -B scripts/apply_dankbar_preset.py --check`: passed against the
  applied user configuration.
- DMS was stopped, the preset reapplied, and `dms.service` started again;
  the preset check passed after startup.
- `dms ipc` could not retrieve IPC targets and `hyprctl configerrors` returned
  `Couldn't set socket timeout (2)`. No Hyprland reload was performed.

## Limitations

- The visual bar could not be inspected live in this session; clipping,
  actual module geometry, and both monitor scales remain to be verified in the
  running desktop.
- DMS applies its custom theme globally, not just to DankBar. This is the
  supported way to consume the shared palette without overriding DMS QML.
- The generated DMS theme uses static Graphite Blue. Phase 19's dynamic color
  overlay is not applied to DankBar and remains a future integration.
- Native DankBar widget glyph aliases are not configurable through the DMS
  settings API; the widgets keep their bundled Material Symbols names.
- The 43PR Phase 16 audit note remains absent from this checkout.

## Files changed

- `themes/templates/dms-theme.json.tmpl` — shared-token to DMS-role mapping.
- `scripts/build-theme.py` — generates/checks the DMS theme alongside Lua.
- `dms/themes/graphite-blue/theme.json` — generated DMS custom theme.
- `dms/presets/dankbar-43pr.json` — native widget and visual profile.
- `scripts/apply_dankbar_preset.py` — safe profile installer/checker.
- `tests/theme/test_theme.py` and `tests/theme/test_dankbar_preset.py` —
  generation and safe-application tests.
- `docs/architecture/theme-system.md` — DMS theme consumer.
- `docs/architecture/typography-icons.md` — native DMS icon alias boundary.
- `docs/phases/20-dankbar-visual-shell.md` — this phase record.

## Commit

Dedicated Phase 20 commit; see the final report.
