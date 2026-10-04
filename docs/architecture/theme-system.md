# Theme system architecture

## Responsibilities

`themes/presets/default.json` is the versioned source for the project's color,
typography, and iconography roles. `themes/tokens/schema.json` defines the
required roles and their value formats. Component templates translate those
roles to component-specific configuration; they do not define another
palette.

The current generation path is:

```text
themes/presets/default.json
        + themes/tokens/schema.json
        + themes/templates/hyprland-theme.lua.tmpl
                    │
                    ▼
          scripts/build-theme.py
                    │
                    ▼
hypr/.config/hypr/modules/theme_tokens.lua
                    │
                    ▼
hypr/.config/hypr/modules/appearance.lua
```

The generated Lua module is committed so Hyprland can load the configuration
without running a generator during startup. It contains all preset token
groups; Hyprland currently consumes its color mapping. After changing the
preset or its template, run `python3 scripts/build-theme.py --write`; use
`--check` to detect stale generated output.

## Semantic token contract

Schema version 2 keeps opaque `#RRGGBB` sRGB colors grouped by role:

- `surfaces`: `background`, `surface`, `surface_variant`, `surface_elevated`.
- `text`: `primary`, `secondary`, `muted`, `disabled`.
- `accents`: `primary`, `secondary`, `selection`, `focus`.
- `semantic`: `success`, `warning`, `error`, `info`.
- `borders`: `default`, `subtle`.

Typography roles are in the same preset: UI and monospace families with
ordered fallbacks, a seven-step logical-pixel scale, named weights, and
relative line heights. Iconography uses DMS-bundled Material Symbols Rounded
with lowercase ligature names and a small semantic alias map. Opacity belongs
to component mappings, not the palette. Adding or renaming required roles
needs a schema version decision, validator/test updates, template updates,
and migration notes.

## Matugen and DMS

DMS already owns the live wallpaper-driven Matugen workflow. Its current
generated files include `~/.config/hypr/dms/colors.lua`, GTK styles, and Kitty
colors. `modules/dms.lua` loads `dms.colors` after `modules/appearance.lua`, so
DMS remains authoritative for generated active and inactive window/group
borders when its colors module exists. The semantic preset supplies the
project's stable Hyprland defaults, including the shadow color, and fallback
border values. It does not replace DMS's generated wallpaper palette.

This phase intentionally adds no second Matugen config or user template and
does not invoke DMS generation. The installed `dms matugen` reports GTK,
Hyprland, and Kitty integration as detected, and its existing generated
outputs remain in control. A later integration can map Matugen's generated
roles into this semantic contract once that can be done without competing
with DMS's own outputs.

## Current consumers and boundaries

Hyprland is the first repository-managed consumer of the generated module.
DMS already bundles and uses Inter Variable, FiraCode Nerd Font, and Material
Symbols Rounded; the selected token roles record those defaults and the
system fallbacks. GTK continues to use system font and icon-theme settings.
Kitty continues to resolve its unspecified `monospace` family through
Fontconfig. Phase 18 documents the distinction between the shared contract
and the existing component settings; it does not introduce another font or
icon generator.
