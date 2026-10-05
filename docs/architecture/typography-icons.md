# Typography and iconography

## Source of truth

Typography and iconography live beside color roles in
`themes/presets/default.json`, validated by `themes/tokens/schema.json` and
rendered into `hypr/.config/hypr/modules/theme_tokens.lua`. The contract is
version 2. Keep family names, fallback order, scale, weights, line heights,
icon aliases, and their QML usage in that preset rather than duplicating them
in application templates.

## Font roles

- **UI:** DMS's bundled Inter Variable. Fallback order for system components:
  Adwaita Sans, Noto Sans, generic sans-serif.
- **Monospace:** DMS's bundled FiraCode Nerd Font. Fallback order for system
  components: Adwaita Mono, Noto Sans Mono, generic monospace.

DMS's `Fonts.qml` loads its own Inter and Fira Code assets, so `fc-match`
cannot report those embedded fonts as installed system families. Tests verify
the bundled files exist and that the first system fallbacks resolve through
Fontconfig. The bundled FiraCode Nerd file is Regular-only; use the fallback
chain for applications that require additional installed weights.

Sizes are logical-pixel roles from `display` through `micro`. Weights use the
numeric CSS/Qt convention (400, 500, 600, 700). Line heights are multipliers.
These are design tokens for consumers; DMS keeps its own scale and components
that are not configured from the repository are not changed automatically.

## Icon roles

DMS bundles Material Symbols Rounded and accepts ligature names. In QML,
`DankIcon.name` receives the name directly; `AppIconRenderer.iconValue` uses
the `material:` prefix. Reuse the semantic aliases in the preset and avoid
scattering Unicode code points in QML. DMS also bundles FiraCode Nerd Font for
specialized file-type glyphs; that is not the general shell icon API.

Native DankBar widgets currently own their Material Symbols names internally;
the DMS bar settings do not expose a per-widget alias mapping. The shared
aliases remain the contract for project-owned QML consumers and are not
duplicated into a parallel glyph configuration for native widgets.

GTK and file/application icons continue to use the user's system icon theme.
Material Symbols are not a replacement for a complete desktop icon theme.

## Validation

Run:

```bash
python3 -B scripts/build-theme.py --check
python3 -B -m unittest discover -s tests/theme -v
```

The tests check token structure, family fallback resolution, bundled DMS font
assets, and that each Material alias shapes to its named glyph with
`hb-shape`.
