# Wallpaper and dynamic theme architecture

## Responsibilities

| Component | Responsibility |
| --- | --- |
| DMS | Selects and renders wallpapers; triggers its existing Matugen workflow. |
| Matugen | Produces one wallpaper-derived palette for DMS built-in and user templates. |
| Semantic theme contract | Defines stable color role names and validates the dynamic color overlay against contract v2. |
| Promotion hook | Validates the generated candidate and atomically updates the last-known-good runtime overlay. |
| Graphite Slate | Static fallback used by repository-managed theme consumers when no valid wallpaper palette is available. |
| Hyprland | Uses the committed Graphite Slate module as fallback and loads DMS-generated border colors when present. |

## Data flow

```text
DMS wallpaper selection / wallpaper change
                  │
                  ▼
       DMS Matugen generation (single run)
          ┌───────┴────────┐
          ▼                ▼
   DMS built-in       user template
   application files       │
                           ▼
                 dynamic-colors.pending.json
                           │
                 validate + atomic replace
                           ▼
       ~/.local/state/hyprland/dynamic-colors.json
```

The user template uses Material color roles for surfaces, text, accents, and
borders, and DMS's `dank16` colors for success/warning/error/info. It emits
only color tokens. Typography and iconography continue to come from the
selected static theme preset; consumers merge the color overlay rather than
treating it as a complete theme preset.

## Failure and fallback behavior

- **Matugen or wallpaper input fails:** the post-hook does not promote a new
  overlay; the last-known-good file remains unchanged.
- **Generated JSON or color roles are invalid:** validation fails before
  replacement; the existing overlay remains unchanged.
- **No dynamic overlay exists:** current Hyprland continues using the
  committed Graphite Slate token module. Future consumers must use that same
  static preset as their fallback.
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
then writes a temporary file beside the destination and uses `os.replace`.
No separate Matugen process, polling loop, wallpaper daemon, or Hyprland reload
is introduced.

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

This phase exports and validates the dynamic colors. It does not apply them to
the active Hyprland session, reload Hyprland, change DMS's theme mode, or
configure DankBar. Those consumers can be wired in later phases after the
active and repository configuration paths are reconciled.
