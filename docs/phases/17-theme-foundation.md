# Phase 17 — Theme Foundation

## Status

Implemented in the repository. Runtime validation against the active
Hyprland configuration was unavailable in this environment.

## Objective

Define a versioned semantic token contract, one dark preset, and a reproducible
path for consuming the preset in Hyprland while preserving the existing DMS
and Matugen flow.

## Scope

Included the token schema and preset, a small generator and template for
Hyprland, validation tests, Hyprland appearance wiring, and this phase and
architecture documentation. No DMS overrides, DMS settings, user Matugen
configuration, Kitty/GTK configuration, GPU settings, monitors, or workspace
behavior were changed.

## Existing System

The repository had no `themes/` tree, token contract, Matugen configuration,
or phase-specific documentation for Phase 16. `docs/workspace-overview.md`
was the existing overview architecture reference. Matugen 4.2.0 and DMS are
installed. `dms matugen check` detected GTK, Hyprland, and Kitty integrations.
DMS's generated `~/.config/hypr/dms/colors.lua` is loaded after
`modules/appearance.lua`, allowing DMS to override the border defaults.

## Architecture

See [theme-system.md](../architecture/theme-system.md). The committed JSON
preset is validated and rendered by `scripts/build-theme.py` into
`hypr/.config/hypr/modules/theme_tokens.lua`. `appearance.lua` consumes its
Hyprland mapping. DMS retains ownership of its dynamic wallpaper-derived
colors and generated component files.

## Token Contract

All preset colors are opaque `#RRGGBB` strings. The schema requires surface,
text, accent, semantic-state, and border roles. Component templates define
opacity. Validation enforces minimum contrast ratios of 7:1 for primary text,
4.5:1 for secondary text, and 3:1 for muted text against the background.

## Theme Structure

```text
themes/
├── presets/default.json
├── templates/hyprland-theme.lua.tmpl
└── tokens/schema.json
```

## Default Preset

`default.json` defines the dark “Graphite Blue” base: near-black background,
quiet elevated surfaces, cool high-contrast text, a controlled blue accent,
mint secondary accent, restrained borders, and semantic status colors. It
uses the supplied visual reference as direction rather than copying its
values. The chosen surfaces and text were checked against the contrast
thresholds enforced by the validator.

## Matugen Integration

Matugen is already used through DMS to generate wallpaper-derived GTK,
Hyprland, and Kitty outputs. No independent Matugen config or template was
added, and no generation was triggered. DMS remains the runtime source for
its generated borders and application colors; the repository preset is the
stable Hyprland base/fallback. A direct mapping from DMS/Matugen-generated
roles to the versioned semantic contract remains future work because DMS
currently writes and loads its own outputs.

## Component Integration

`appearance.lua` now imports `modules.theme_tokens` for active/inactive border
defaults and the shadow color. The existing later `dms.colors` load continues
to override the border defaults when available. No other component was
modified.

## Validation

- `python3 scripts/build-theme.py --write` generated the Lua token module.
- `python3 -B -m unittest discover -s tests/theme -v`: four tests passed,
  covering the required token contract, invalid/missing values, contrast,
  deterministic and complete rendering, and generated-file consistency.
- `python3 -B scripts/build-theme.py --check`: passed; generated output matches
  the preset and template.
- `hyprctl configerrors` on the active configuration returned no errors.
  `hyprctl reload` was not run because the repository copy has not been
  deployed to `~/.config/hypr`.
- The active `~/.config/hypr/modules/appearance.lua` differs from the
  repository copy; it was preserved and not overwritten. The new generated
  module is therefore not loaded by the active session.
- Existing layout tests and DMS runtime behavior were not changed.

## Files Changed

`themes/tokens/schema.json`, `themes/presets/default.json`,
`themes/templates/hyprland-theme.lua.tmpl`, `scripts/build-theme.py`,
`hypr/.config/hypr/modules/theme_tokens.lua`,
`hypr/.config/hypr/modules/appearance.lua`, `tests/theme/test_theme.py`,
`docs/architecture/theme-system.md`, and this file.

## Design Decisions

- JSON is the authored palette format because it is easy to inspect and
  validate independently of the component consuming it.
- The generated Lua file is committed to avoid runtime generation and startup
  dependencies.
- DMS remains responsible for wallpaper-based Matugen output; this phase does
  not create competing templates or regenerate the user's current colors.
- Component-specific opacity is applied in the Hyprland template, keeping
  alpha out of the shared semantic token values.

## Problems Encountered

The first template placeholder expression treated `_hex` as part of a token
name. The renderer expression was corrected, and the full theme test suite
then passed.

## Known Limitations

- DMS-generated borders can override the preset's border defaults.
- DMS, GTK, and Kitty do not yet directly consume this repository's semantic
  token schema; they continue to use DMS/Matugen's existing generated output.
- The active Hyprland config differs from the repository copy, and the
  changes were not copied into the active configuration or validated by a
  live reload.

## Future Work

- Define a safe adapter from DMS/Matugen semantic roles to the project token
  contract without competing with DMS-generated files.
- Extend component templates only when an integration can be validated and
  does not introduce duplicate palette sources.

## Commit

Dedicated Phase 17 commit; hash recorded in the final report.
