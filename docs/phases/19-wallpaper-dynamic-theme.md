# Phase 19 — Wallpaper & Dynamic Theme Integration

## Status

Implemented as the dynamic color export layer. DMS remains the wallpaper and
Matugen authority. Automatic application to Hyprland is deliberately deferred
because the active Hyprland config differs from the repository copy and the
live reload/application path was not established.

## Context

Phase 17 introduced Graphite Blue as the stable static theme and Phase 18
added typography and icon roles. DMS already manages wallpaper-driven Matugen
generation. Phase 19 adds one user template that exports a color overlay from
that same palette without introducing a second Matugen invocation.

The referenced `docs/phases/16-43pr-audit.md` was not present in this checkout.
Phase 17 and 18 records and the current repository/system state were used.

## Existing system found

- Fedora environment has Matugen 4.2.0 and DMS installed.
- `dms matugen check` detects GTK, Hyprland, and Kitty integrations.
- DMS's generated output includes `~/.config/hypr/dms/colors.lua`, GTK
  `dank-colors.css` files, and Kitty colors. Those files were inspected but
  not modified.
- The installed DMS supports user Matugen templates, and its source defaults
  `runUserMatugenTemplates` to true. The runtime preference could not be read
  because DMS IPC had no accessible targets in this environment.
- `wallpaperCarousel` 0.8.4 is installed under
  `~/.config/DankMaterialShell/plugins/wallpaperCarousel` and pinned in
  `plugins.lock.json`. Its DMS adapter selects through DMS `SessionData`; the
  runtime plugin-enabled state could not be confirmed.
- DMS also includes a built-in wallpaper settings/picker flow.
- No `~/.config/matugen` existed before this phase, so there was no user
  Matugen config to merge or overwrite. It now links to the versioned package
  added in this phase.
- No `~/Pictures/Wallpapers` or repository wallpaper files exist. One screenshot
  was present, but no personal image was used or added to the repository.
- `awww`, `swww`, `swaybg`, and `hyprpaper` are absent. No wallpaper package was
  installed.
- The active Hyprland appearance file differs from the repository version.

## Architecture

```text
DMS wallpaper selection/change
              ↓
       existing DMS Matugen run
          ┌───┴──────────┐
          ↓              ↓
 DMS built-in outputs  one user template
                            ↓
               dynamic-colors.pending.json
                            ↓
                  validate + atomic promote
                            ↓
          ~/.local/state/hyprland/dynamic-colors.json
```

| Component | Responsibility |
| --- | --- |
| DMS | Wallpaper selection and rendering; starts its current palette generation flow. |
| Matugen | Generates the palette once for DMS built-in and custom user templates. |
| Theme contract | Defines semantic color role names and validates the v2 overlay. |
| Graphite Blue | Static fallback already used by the repository-managed Hyprland appearance. |
| Hyprland | Continues using the static committed theme; no dynamic reload/apply was added. |

The output file is a color-only overlay with the same semantic group and role
names as the contract. Typography and iconography are not copied or generated;
they remain sourced from the static preset.

## Wallpaper source and renderer

DMS is responsible for the wallpaper flow. The optional Carousel plugin uses
DMS's wallpaper state and setter API; no external renderer or picker was
added. The installed plugin and its pin are confirmed, but its enablement and
current wallpaper could not be checked because DMS IPC was unavailable.

## Matugen and template activation

`matugen/.config/matugen/config.toml` registers a single user template. The
repository package is linked to `~/.config/matugen`. DMS's
**Run User Templates** option must remain enabled; its source default is true,
but the runtime value could not be inspected.

The template uses Material dark roles for surfaces, text, accents, and
borders. It uses DMS-enriched `dank16` slots for semantic success, warning,
error, and info colors. DMS invokes these as part of its existing Matugen run;
the post-hook only validates and promotes output and never invokes Matugen.

## Validation and atomicity

Matugen writes the candidate to
`~/.cache/DankMaterialShell/dynamic-colors.pending.json`. The hook checks:

- schema version, source, mode, exact groups and roles;
- opaque `#RRGGBB` values;
- the existing text contrast thresholds against the generated background.

Only a valid candidate replaces
`~/.local/state/hyprland/dynamic-colors.json`. The replacement uses a temporary
file in the same directory followed by `os.replace`; malformed palettes leave
the previous valid file untouched. A failed Matugen image run does not reach
the successful template post-hook and therefore cannot replace that file.

If the dynamic file is absent, the committed Graphite Blue theme remains the
static fallback. No DMS or Hyprland output is rewritten by the promoter.

## State

- Versioned source: `matugen/.config/matugen/config.toml` and
  `matugen/.config/matugen/templates/dynamic-colors.json.tmpl`.
- Versioned schemas and validation: `themes/tokens/` and `scripts/`.
- Generated candidate: `~/.cache/DankMaterialShell/dynamic-colors.pending.json`.
- Generated last-known-good overlay: `~/.local/state/hyprland/dynamic-colors.json`.
- The generated files are runtime state and must not be versioned.

## Configuration divergence and application boundary

The dynamic overlay is exported but not loaded by `appearance.lua`. The active
file differs from the repo file, and changing it or adding a Hyprland reload
hook would be a larger runtime integration decision. Accordingly this phase
does not modify either active or versioned Hyprland modules and does not reload
Hyprland. DMS continues to apply its own colors through its current flow.

## Validation

- `matugen --version`: Matugen 4.2.0.
- `dms matugen check`: GTK, Hyprland, and Kitty detected.
- `python3 -B scripts/build-theme.py --check`: passed.
- `python3 -B -m unittest discover -s tests/theme -v`: 11 tests passed,
  including Matugen generation, valid promotion, invalid wallpaper retention,
  and malformed candidate rejection.
- Matugen was run with the production user-template config and a temporary
  `HOME`; output was promoted and validated without touching user state.
- `python3 -m json.tool themes/tokens/schema.json`: passed.
- `python3 -m json.tool themes/tokens/dynamic-colors.schema.json`: passed.
- `git diff --check`: passed.
- `hyprctl configerrors`: attempted; unavailable because the session socket
  returned `Couldn't set socket timeout (2)`.
- No `hyprctl reload` was run.

## Files changed

- `matugen/.config/matugen/config.toml` — one DMS user-template registration.
- `matugen/.config/matugen/templates/dynamic-colors.json.tmpl` — maps the
  existing Matugen palette to semantic color roles.
- `scripts/promote_dynamic_theme.py` — validates and atomically promotes the
  runtime candidate.
- `scripts/build-theme.py` — validates semantic color overlays and schema
  alignment.
- `themes/tokens/schema.json` — adds the dynamic overlay schema definition.
- `themes/tokens/dynamic-colors.schema.json` — standalone overlay schema ref.
- `tests/theme/test_dynamic_theme.py` — schema, generator, promotion, and
  failure-retention tests.
- `docs/architecture/theme-system.md` — updates the DMS/Matugen relationship.
- `docs/architecture/wallpaper-theme.md` — records the permanent data-flow and
  fallback decision.
- `docs/phases/19-wallpaper-dynamic-theme.md` — this phase record.

## Limitations and future work

- The DMS runtime toggle for user templates, plugin enablement, and active
  wallpaper were not readable through IPC here.
- A consumer must validate and merge this color overlay with static Graphite
  Blue. Hyprland and DankBar do not consume it yet.
- Automatic live application to Hyprland needs a separate decision about
  configuration divergence and reload behavior.
- The desktop had no dedicated wallpaper collection to use for visual
  validation; a synthetic image was used in the isolated Matugen test.

## Commit

Dedicated Phase 19 commit; see Git history for its hash.
