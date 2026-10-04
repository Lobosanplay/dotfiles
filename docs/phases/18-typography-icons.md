# Phase 18 — Typography & Icons

## Status

Implemented in the repository and validated against the installed DMS font
assets and system fontconfig. DMS/Kitty/GTK runtime settings were not changed.

## Objective

Extend the Phase 17 theme contract with real font, scale, weight, line-height,
and icon roles without installing fonts or adding another visual token source.

## Scope

Inventory and contract work only, plus validation and documentation. The
existing DMS/Quickshell, GTK, and Kitty configurations remain unchanged. No
Hyprland behavior, workspace logic, or `/usr/share` files were modified.

## Existing Font Inventory

- Fontconfig is available (`fc-list`, `fc-match`).
- DMS loads bundled Inter Variable for UI text and bundled FiraCode Nerd Font
  for monospace text. The FiraCode asset packaged by the installed DMS is the
  Regular file.
- System fallbacks Adwaita Sans, Noto Sans, Adwaita Mono, and Noto Sans Mono
  resolve locally. Current GNOME interface settings are Adwaita Sans 11 and
  Adwaita Mono 11.
- Kitty sets `font_size 12` but no `font_family`; Fontconfig resolves its
  generic `monospace` family to Noto Sans Mono. Kitty configuration is not
  versioned in this repository.
- GTK settings files do not set a font family; GTK inherits the current
  desktop font settings. Hyprlock has no configuration in the repository or
  under the inspected `~/.config/hypr` tree.

The referenced Phase 16 document `docs/phases/16-43pr-audit.md` is absent from
the repository. The repository's tracked history and Phase 17 docs were used
for context; no Phase 16 document was invented.

## Existing Icon Inventory

- DMS bundles Material Symbols Rounded and FiraCode Nerd Font internally.
- The workspace overview accepts Material Symbol names and renders them with
  DMS's `DankIcon` component.
- DMS's `AppIconRenderer` accepts `material:<name>` for Material Symbols.
- The desktop icon theme is `Magna-Dark-Icons`; GTK continues to use it for
  application and file icons.
- No system-installed JetBrains Mono, Nerd Font family, or standalone Material
  Symbols family resolves through Fontconfig; DMS's bundled copies are
  available inside Quickshell only.

## Selected Typography

- UI primary: DMS-bundled Inter Variable.
- UI system fallback: Adwaita Sans → Noto Sans → generic sans-serif.
- Monospace primary: DMS-bundled FiraCode Nerd Font.
- Monospace system fallback: Adwaita Mono → Noto Sans Mono → generic
  monospace.

The selection preserves the fonts DMS already uses and connects system
components to installed families. No font packages were installed.

## Typography Hierarchy

The preset defines logical-pixel roles: display 32, title 20, heading 16,
body 14, label 12, caption 11, and micro 10. Weights are regular 400, medium
500, semibold 600, and bold 700. Relative line-height roles are compact 1.2,
normal 1.4, and relaxed 1.55. DMS's existing defaults align to its own
small/medium/large/xlarge 12/14/16/20 scale; these files do not override its
settings or alter its scale.

## Typography Tokens

Added to the existing versioned `themes/presets/default.json` and
`themes/tokens/schema.json`, not to a parallel token file. The generated Lua
theme module exposes the same typography data as the color roles.

## Icon Strategy

Material Symbols Rounded is the general DMS shell icon system, using semantic
aliases mapped to lowercase ligature names. The small alias set covers close,
settings, workspace, terminal, code, browser, and music. DMS's Nerd Font is
reserved for its specialized file-type glyphs. GTK continues to use the
desktop icon theme.

The contract documents the existing QML forms: `DankIcon.name` takes a
ligature name; `AppIconRenderer.iconValue` takes `material:<name>`. It contains
no raw Unicode glyph values.

## Icon Tokens

The aliases and DMS API forms live in the `iconography` section of the
existing theme preset. Tests shape each alias against the installed bundled
Material Symbols font.

## Fallback Strategy

UI and monospace fallbacks are ordered in the preset and verified with
`fc-match`. DMS's icon fonts are bundled with DMS; GTK keeps the current
desktop icon theme. A Material ligature name is not a fallback for a missing
application/file icon; those use the desktop icon theme.

## Component Integration

No component settings required changes: DMS already loads the selected
bundled families and Material font by default; GTK already uses Adwaita Sans
and Adwaita Mono from desktop settings. Kitty continues using its existing
unconfigured `monospace` fallback, which resolves to Noto Sans Mono. The
contract and generated module now expose the chosen values for future
versioned consumers. This phase does not write to personal DMS/Kitty settings.

## Validation

- `fc-match` confirmed the selected system fallback families.
- Tests confirmed DMS's Inter Variable, FiraCode Nerd Font, and Material
  Symbols font assets are present.
- `hb-shape` successfully shaped all seven configured Material ligature names.
- `python3 -B scripts/build-theme.py --check`: passed.
- `python3 -B -m unittest discover -s tests/theme -v`: seven tests passed.
- `node --test 'tests/layout/*.test.js'`: both existing test files passed.
- `hyprctl configerrors`: no errors in the active configuration. The
  repository's Phase 17 `appearance.lua` remains different from the active
  file, so no reload was run; Phase 18 does not edit active compositor
  configuration.

## Files Changed

- `themes/presets/default.json` — schema v2 typography and iconography tokens.
- `themes/tokens/schema.json` — validation schema for the new token groups.
- `themes/templates/hyprland-theme.lua.tmpl` — emits typography and icon tokens.
- `scripts/build-theme.py` — validation and JSON-to-Lua generation.
- `hypr/.config/hypr/modules/theme_tokens.lua` — regenerated theme module.
- `tests/theme/test_theme.py` — fallback, bundled asset, ligature, and contract tests.
- `docs/architecture/theme-system.md` — updated shared theme architecture.
- `docs/architecture/typography-icons.md` — font and icon usage contract.
- `docs/phases/18-typography-icons.md` — this implementation record.

## Design Decisions

- Reuse DMS's bundled Inter, FiraCode Nerd Font, and Material Symbols instead
  of installing equivalent global fonts.
- Use Adwaita/Noto system fallbacks already installed and used by this Fedora
  setup.
- Keep color, typography, and icon roles in one theme preset and increment
  its schema version to 2.
- Do not modify Kitty or DMS settings that are not tracked in this repository.
- Keep the system icon theme for GTK/application icons; Material Symbols serve
  shell glyphs and do not replace full icon-theme coverage.

## Problems Encountered

The Phase 16 audit document referenced by the brief is missing from the
repository. The available Phase 17 and workspace architecture documentation
were used instead.

## Known Limitations

- DMS uses its own bundled fonts and settings API; the repository contract
  documents those defaults but does not write DMS settings.
- Kitty and GTK are not versioned as repository consumers yet.
- DMS's bundled FiraCode Nerd Font asset is Regular-only; other weights may be
  synthesized unless a system fallback is selected.
- The semantic alias set is intentionally small and covers only common shell
  functions.

## Future Work

- Add explicit DMS and Kitty consumers when their configuration files can be
  managed in the repository without replacing user-generated settings.
- Expand the icon aliases only as components need them.
- Revisit line-height roles when later UI components consume them.

## Commit

Dedicated Phase 18 commit; see the Git log for its hash.
