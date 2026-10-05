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
generation flow in Dynamic theme mode. Its built-in templates continue to
produce outputs such as `~/.config/hypr/dms/colors.lua`, GTK styles, and Kitty
colors. DMS/Matugen also runs the repository's user template from the same
generation and emits a color-only semantic overlay at
`~/.local/state/hyprland/dynamic-colors.json`. The post-hook validates and
atomically promotes that overlay, then renders an owned Lua consumer and uses
the public Hyprland `hyprctl eval` interface for immediate application. It
does not invoke Matugen again, overwrite DMS output, or reload Hyprland.

The overlay is separate from the authored Graphite Slate preset and from the
generated `theme_tokens.lua`. Graphite Slate remains Hyprland's static
fallback. Hyprland uses the validated semantic projection for wallpaper-based
border colors; DMS, DankBar, GTK, and Kitty use DMS's native outputs from the
same Matugen run. The project no longer loads DMS's independent
`dms.colors.lua` into Hyprland, avoiding two competing writers for border
colors. See [wallpaper-theme.md](wallpaper-theme.md) and
`docs/phases/22-live-dynamic-theme.md` for the runtime lifecycle.

## Current consumers and boundaries

Hyprland consumes static Graphite Slate through the generated Lua token module
and overrides its border roles with a generated module only when the validated
dynamic overlay exists. DMS is configured for its native Dynamic theme mode;
the Graphite Slate custom theme remains installed and can be selected manually
as a static alternative. DMS continues to own its component typography and icons:
its bundled Inter and Material Symbols already match the selected UI family
and icon provider, but individual native widget glyphs are not remapped through
the repository's alias table. GTK continues to use system font and icon-theme
settings while its colors come from DMS/Matugen. Kitty continues to resolve
its unspecified `monospace` family through Fontconfig and uses the
DMS-generated color file. The semantic dynamic overlay is consumed by
Hyprland after schema and contrast validation; it is not a second generator
for GTK, Kitty, or DMS.
