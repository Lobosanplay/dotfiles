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
        + component templates
                    │
                    ▼
          scripts/build-theme.py
             ┌──────┴──────┐
             ▼             ▼
      Hyprland Lua    DMS custom theme
             │             │
      appearance.lua  DankBar and DMS UI
```

The generated Lua module is committed so Hyprland can load the configuration
without running a generator during startup. It contains all preset token
groups; Hyprland currently consumes its color mapping. After changing the
preset or a component template, run `python3 scripts/build-theme.py --write`;
use `--check` to detect stale generated output. The DMS theme output translates
the same semantic roles to DMS's native custom-theme color names. A small
profile applier selects that theme and configures the existing DankBar without
adding a Quickshell shell or copying DMS components. It preserves unrelated
DMS settings and creates a one-time settings backup before applying.

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

The overlay is separate from the authored Graphite Slate preset and from the
generated `theme_tokens.lua`. The static preset remains the fallback and
continues to feed the repository-managed Hyprland appearance. The active
Hyprland setup also loads DMS's generated `dms.colors.lua` when present, which
provides wallpaper-derived border colors. Future consumers should use the
dynamic overlay only after validation and otherwise fall back to Graphite
Slate. See [wallpaper-theme.md](wallpaper-theme.md) and
`docs/phases/19-wallpaper-dynamic-theme.md` for the full lifecycle.

## Current consumers and boundaries

Hyprland consumes the generated Lua color mapping. DMS consumes the generated
custom theme through its supported `customThemeFile` setting; the profile
applier selects it. DMS continues to own its component typography and icons:
its bundled Inter and Material Symbols already match the selected UI family
and icon provider, but individual native widget glyphs are not remapped through
the repository's alias table. GTK continues to use system font and icon-theme
settings. Kitty continues to resolve its unspecified `monospace` family
through Fontconfig. The dynamic Matugen overlay remains an export only; this
consumer uses the static Graphite Slate preset as its fallback.
