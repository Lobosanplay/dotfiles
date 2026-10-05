# Wallpaper and dynamic theme architecture

## Responsibilities

| Component | Responsibility |
| --- | --- |
| DMS | Selects and renders wallpapers; Dynamic theme mode triggers its existing Matugen workflow. |
| Matugen | Produces one wallpaper-derived palette for DMS built-in and user templates. |
| Semantic theme contract | Defines stable color role names and validates the dynamic color overlay against contract v2. |
| Promotion hook | Validates the candidate, atomically updates the last-known-good JSON and Lua consumer, and applies Hyprland colors through `hyprctl eval` when the active config has the bridge. |
| Graphite Slate | Static fallback used by repository-managed theme consumers when no valid wallpaper palette is available. |
| Hyprland | Uses Graphite Slate as fallback and the validated semantic projection for dynamic borders. |
| DMS, DankBar, GTK, Kitty | Consume DMS's native outputs from that same Matugen generation. |

## Wallpaper selection

DMS owns wallpaper rendering and selection. In the current Hyprland setup,
`SUPER+Y` runs `dms ipc call dash toggle wallpaper` and opens/toggles DMS's
built-in wallpaper dashboard. Selecting a wallpaper there invokes DMS's
wallpaper service and its Dynamic Matugen workflow. This is an entry-point
shortcut; there is no dedicated Hyprland shortcut that directly applies the
next wallpaper.

The enabled `wallpaperCarousel` plugin is also available from DMS's Control
Center shortcut grid. Its `shortcut.luau` defines that clickable tile, not a
keyboard binding. The carousel's left/right/Enter/Escape keys operate only
while the overlay is open. No keybinding for the plugin is present in the
versioned Hyprland modules or the user's DMS bind override.

## Data flow

```text
DMS wallpaper selection / wallpaper change
                  │
                  ▼
       DMS Matugen generation (single run, Dynamic theme mode)
          ┌───────┴────────┐
          ▼                ▼
   DMS built-in       user template
   application files       │
                           ▼
                 dynamic-colors.pending.json
                           │
          validate + atomic promotion
                           ▼
       ~/.local/state/hyprland/dynamic-colors.json
                           │
            render atomic Lua module
                           │
             hyprctl eval (no reload)
                           ▼
                     Hyprland
```

The user template uses Material color roles for surfaces, text, accents, and
borders, and DMS's `dank16` colors for success/warning/error/info. It emits
only color tokens. Typography and iconography continue to come from the
selected static theme preset; consumers merge the color overlay rather than
treating it as a complete theme preset.

## Failure and fallback behavior

- **Matugen or wallpaper input fails:** the post-hook does not run; the
  last-known-good JSON and Lua module remain unchanged. DMS retains its
  currently applied palette.
- **Generated JSON or color roles are invalid:** validation fails before
  promotion; the existing overlay and Lua module remain unchanged.
- **No dynamic overlay exists:** the optional dynamic Lua module is absent and
  Hyprland uses Graphite Slate values from its appearance configuration.
- **The semantic bridge cannot apply live:** DMS's native generation remains
  successful; the Lua consumer is retained for the next normal Hyprland
  configuration load. Current live Hyprland borders remain at their prior
  values until then.
- **DMS user templates are disabled or the package is not linked:** no new
  overlay is generated. DMS's own wallpaper and built-in Matugen outputs are
  unaffected.
- **DMS is unavailable:** no wallpaper selection or Matugen generation occurs;
  the static Hyprland theme remains usable.

An invalid wallpaper may be rejected by DMS before its theme flow runs. This
project does not replace or alter DMS's wallpaper renderer.

## State and versioning

- Versioned source: `matugen/.config/matugen/config.toml` and
  `matugen/.config/matugen/templates/dynamic-colors.json.tmpl`.
- Versioned validation: `themes/tokens/dynamic-colors.schema.json`,
  `themes/tokens/schema.json`, and `scripts/build-theme.py`.
- Runtime candidate: `~/.cache/DankMaterialShell/dynamic-colors.pending.json`.
- Runtime last-known-good overlay:
  `~/.local/state/hyprland/dynamic-colors.json`.
- Runtime candidates and overlays are not committed.

The candidate is written outside the consumer path. The promotion script
validates schema version, exact role sets, opaque hex values, and text contrast,
then writes temporary files beside each destination and uses `os.replace`.
It renders only fixed Hyprland settings from validated hex values and applies
them through one `hyprctl eval` call. The script checks that the active config
loads the bridge and that a Hyprland instance is present before applying. No
separate Matugen process, polling loop, wallpaper daemon, or Hyprland reload is
introduced.

The repository package is linked at `~/.config/matugen` (that path was absent
before Phase 19). Keep DMS's **Run User Templates** option enabled. The link
was created with:

```bash
ln -s ~/dotfiles/matugen/.config/matugen ~/.config/matugen
```

Remove that link to disable this project's template. Do not replace an
existing Matugen config: merge the `[templates.dotfiles_semantic_colors]`
entry into it instead.

## Deliberate boundary

The semantic JSON is a projection of DMS's single Matugen run, not a second
palette authority. DMS's Dynamic theme mode feeds its native DMS/DankBar/GTK/
Kitty outputs; the semantic projection feeds Hyprland after validation. The
active and versioned Hyprland files remain separate, and live application is
skipped unless the active config explicitly loads the bridge. This avoids
rewriting user configuration or reloading Hyprland from the Matugen hook.
