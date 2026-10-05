# Phase 22 — Live Dynamic Theme Application

## Status

Implemented and applied to the current session. DMS is in native Dynamic theme
mode. A successful DMS/Matugen run regenerated its native outputs and the
semantic overlay; the validated overlay was applied to the active Hyprland
instance. A separate configuration reload was run afterward to verify
persistence.

## Architecture

```text
DMS wallpaper + Dynamic theme mode
                 │
                 ▼
        one DMS Matugen run
          ┌──────┴─────────┐
          ▼                ▼
     DMS native files    semantic user template
     DMS / DankBar       candidate JSON in cache
     GTK / Kitty                │
                                ▼
                      schema + color validation
                                │
                       atomic last-known-good JSON
                                │
                      generated Lua consumer
                                │
                     hyprctl eval (live apply)
                                ▼
                           Hyprland
```

DMS remains the wallpaper, Matugen, and visual-shell authority. The project
user template is part of that same Matugen execution; it never starts another
Matugen process. DMS owns its GTK and Kitty color files and its shell colors.
DankBar inherits DMS's active theme. A semantic projection exists so Hyprland
can use the project's role names without parsing DMS-specific generated Lua.

## Runtime authority

- **Dynamic source:** one DMS/Matugen generation from the current wallpaper.
  DMS's native outputs are authoritative for DMS/DankBar, GTK, and Kitty.
  The validated semantic JSON from the same Matugen run is authoritative for
  Hyprland's dynamic border roles.
- **Static fallback:** Graphite Slate in `themes/presets/default.json` and the
  appearance configuration. If no validated semantic state exists, the
  optional dynamic module is absent and Hyprland keeps its static appearance.
- The generated `~/.config/hypr/dms/colors.lua` is no longer loaded by the
  project's `modules.dms.lua`; this prevents DMS's border colors and the
  semantic bridge from competing for Hyprland's same settings. DMS still
  generates its native file as part of its standard integration.

## Precedence

For Hyprland:

```text
validated dynamic semantic module
        > Graphite Slate static appearance
```

The dynamic module is generated from `dynamic-colors.json`, and applies only
when the candidate passes the schema, exact-role, hex-color, and contrast
checks. Its active/inactive border, group-border, and groupbar colors map to
`accents.primary`, `borders.default`, and `semantic.error`.

For DMS/DankBar, GTK, and Kitty, the native DMS/Matugen outputs from the same
single generation are used. The static Graphite Slate custom theme remains
installed in DMS settings as a selectable manual theme, but the selected
runtime mode is `dynamic`.

## DMS integration

Installed DMS 1.6.2 source and its public documentation were inspected.
DMS's `Theme` service selects `dynamic` mode and uses its current wallpaper as
the Matugen input. DMS's native generator writes Hyprland, GTK, and Kitty
outputs and supports user Matugen templates. The Matugen worker completed
successfully after the mode change.

DMS documents custom theme JSON as live-reactive, and installed `Theme.qml`
confirms a `FileView` watches the selected custom theme. That route was not
used: loading a changed custom theme also asks DMS to regenerate system themes
from that custom palette, which would not make wallpaper the dynamic source.
DMS's public IPC `settings set` persists settings but the installed IPC
implementation assigns properties directly, without running the normal
settings change hooks. Therefore the one-time selection of Dynamic mode was
followed by DMS's supported `dms restart` command so startup loaded the stored
mode and initiated Matugen. Later wallpaper changes use DMS's normal dynamic
flow; no watcher or polling was added.

Relevant upstream interfaces: [DMS custom themes](https://danklinux.com/docs/dankmaterialshell/custom-themes),
[DMS IPC](https://danklinux.com/docs/dankmaterialshell/keybinds-ipc), and
[Hyprland `hyprctl`](https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl/).

## Matugen integration

The active `~/.config/matugen` symlink points to the versioned config. The
DMS-triggered Matugen run writes the user-template candidate to
`~/.cache/DankMaterialShell/dynamic-colors.pending.json`. Its post-hook calls
`scripts/promote_dynamic_theme.py` with the candidate, canonical state path,
Hyprland Lua output path, and `--apply-live`.

The hook validates first, writes the last-known-good JSON and generated Lua
module with same-directory temporary files and `os.replace`, then attempts one
`hyprctl eval` call. On startup or the next ordinary Hyprland config load,
`modules.dms.lua` optionally requires
`~/.config/hypr/dms/dotfiles_theme.lua`. The generated module contains only
fixed `hl.config` settings and values accepted by the strict `#RRGGBB`
validator; JSON is never executed as Lua.

## Hyprland integration

The versioned and active `modules/dms.lua` both load
`dms.dotfiles_theme` after appearance. The active `hyprland.lua` already loads
`modules.dms`; it was left untouched. The active `modules/dms.lua` was an exact
copy of the repository version before modification. Its original copy is
preserved at `~/.config/hypr/modules/dms.lua.before-phase22`.

For immediate changes, `hyprctl eval` applies the generated `hl.config` table
without a full config reload. The saved generated Lua module makes the same
colors return on the next ordinary configuration load. The post-hook checks
that the active main config loads `modules.dms`, that the active DMS module
loads this bridge, and that an active Hyprland instance is available. If any
check or `hyprctl eval` fails, DMS's native theme generation is unaffected;
the module remains for a later config load and the current live Hyprland
colors stay as they were.

No full `hyprctl reload` is performed by the hook.

## Failure handling

- Matugen/wallpaper failure: the user hook does not promote anything; existing
  dynamic JSON, generated Lua, and currently applied colors remain unchanged.
- Invalid candidate: schema/role/color/contrast checks reject it before either
  output is replaced; the candidate remains for diagnosis and previous valid
  state is preserved.
- Output replacement failure: the promoter attempts to restore the prior
  JSON/Lua pair atomically; it does not remove the candidate on failure.
- No prior dynamic state: no dynamic module is loaded and Graphite Slate
  remains Hyprland's fallback.
- Live apply unavailable or refused: DMS generation completes independently;
  the generated module remains available for the next normal Hyprland config
  load. No reload is attempted.
- DMS stopped: the last active colors remain in the compositor. On next DMS
  startup, its Dynamic mode regenerates native outputs from the wallpaper; if
  Matugen is unavailable, the semantic last-known-good remains available.

## Atomic state

The canonical dynamic JSON remains at
`~/.local/state/hyprland/dynamic-colors.json`; the generated Hyprland consumer
is `~/.config/hypr/dms/dotfiles_theme.lua`. Both are runtime state and are not
tracked. Each file is written through a temporary file in the destination
directory and atomically replaced. If writing either fails, the promoter
attempts to restore both prior files and leaves the candidate in place. The
existing schema and contrast validation are unchanged.

## Consumers

- **Hyprland:** generated semantic Lua projection for dynamic borders; static
  Graphite Slate appearance when the projection does not exist.
- **DMS/DankBar:** DMS native Dynamic theme colors.
- **GTK:** DMS/Matugen-generated GTK CSS.
- **Kitty:** DMS/Matugen-generated `dank-theme.conf`, still included by the
  existing Kitty config; the dotfiles opacity include remains independent.

## Scope and exclusions

Changed only the theme profile, Matugen post-hook, runtime promoter, DMS
Hyprland adapter, theme documentation, and theme tests. No WorkspaceGraph,
WorkspaceOverview, keybind, monitor, NVIDIA/PRIME, wallpaper renderer, or
DankBar architecture changes were made. No package was installed and no file
under `/usr/share` was modified.

## Validation

- `python3 -B -m unittest discover -s tests/theme -v`: 22 tests passed,
  including candidate rejection, last-known-good retention, runtime Lua
  determinism, active-config bridge guards, and rollback after a simulated
  runtime write failure.
- `python3 -B scripts/build-theme.py --check`: passed.
- `python3 -B scripts/build-theme.py --check-dynamic ~/.local/state/hyprland/dynamic-colors.json`: passed after the real DMS/Matugen generation.
- DMS settings verified over IPC: `currentThemeName=dynamic`,
  `currentThemeCategory=dynamic`, `runUserMatugenTemplates=true`.
- DMS restarted with `dms restart`; `dms.service` returned to `active`.
- DMS log confirms Dynamic image mode, one Matugen worker completion, native
  output generation, and successful semantic post-hook.
- Runtime JSON, Lua bridge, DMS Hyprland colors, GTK CSS, and Kitty colors all
  received fresh timestamps from the same generation.
- `hyprctl getoption` confirmed live active/inactive borders and group colors
  match the generated semantic bridge.
- `hyprctl configerrors`: no output/errors before and after reload;
  `hyprctl reload` returned `ok`. The Matugen hook itself applies through
  `hyprctl eval` and does not initiate a full reload.
- The existing DMS overlay and workspace/layout tests were not altered.

## Limitations

- A failed `hyprctl eval` leaves Hyprland at its previous live palette until
  the next normal configuration load; the DMS shell and app theme generation
  remain unaffected.
- GTK/Kitty generated outputs were checked for fresh generation and expected
  files, but application windows were not visually inspected in this run.
- `hyprctl eval` is a runtime update and is not itself persistent; the
  generated Lua consumer supplies persistence across normal config loads.

## Files changed

- `dms/presets/dankbar-43pr.json`
- `docs/architecture/theme-system.md`
- `docs/architecture/wallpaper-theme.md`
- `docs/phases/22-preflight.md`
- `docs/phases/22-live-dynamic-theme.md`
- `hypr/.config/hypr/modules/dms.lua`
- `matugen/.config/matugen/config.toml`
- `scripts/apply_dankbar_preset.py`
- `scripts/promote_dynamic_theme.py`
- `tests/theme/test_dankbar_preset.py`
- `tests/theme/test_dynamic_theme.py`
