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

DMS owns wallpaper selection/rendering and starts the existing Matugen
generation flow. Its built-in templates continue to produce outputs such as
`~/.config/hypr/dms/colors.lua`, GTK styles, and Kitty colors. The repository
adds one DMS user template that consumes that same Matugen render and emits a
color-only semantic overlay at
`~/.local/state/hyprland/dynamic-colors.json`. It does not invoke Matugen or
replace any DMS output. A post-hook validates the candidate and promotes it
atomically; invalid candidates leave the last valid overlay untouched.

The overlay is separate from the authored Graphite Blue preset and from the
generated `theme_tokens.lua`. The static preset remains the fallback and
continues to feed the current Hyprland appearance. No automatic reload or
runtime application of the overlay is wired into Hyprland yet: the active
configuration differs from the repository version, and a reliable live
application path needs its own validation. Future consumers should use the
dynamic overlay only after validation and otherwise fall back to Graphite
Blue. See [wallpaper-theme.md](wallpaper-theme.md) and
`docs/phases/19-wallpaper-dynamic-theme.md` for the full lifecycle.

## Current consumers and boundaries

Hyprland is the first repository-managed consumer of the generated module.
DMS already bundles and uses Inter Variable, FiraCode Nerd Font, and Material
Symbols Rounded; the selected token roles record those defaults and the
system fallbacks. GTK continues to use system font and icon-theme settings.
Kitty continues to resolve its unspecified `monospace` family through
Fontconfig. Phase 18 documents the distinction between the shared contract
and the existing component settings; it does not introduce another font or
icon generator.
