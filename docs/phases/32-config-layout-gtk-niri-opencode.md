# Phase 32 — Configuration Layout, GTK Surfaces, and Niri App Rules

**Status:** In progress — the OpenCode sidebar request and live visual checks
remain unresolved.

## Objective

Flatten managed application configuration under repository `.config/`,
provide a safe symlink helper, make GTK3/GTK4 surfaces translucent, and float
the requested applications under Niri. Audit adjacent directories without
discarding tests, theme inputs, DMS overrides, or wallpaper assets.

## Scope and decisions

- Move GTK, Kitty, Matugen, Niri, and systemd configuration to `.config/`.
- Preserve active tests and DMS/theme sources; they are referenced by scripts,
  tests, generated output, or the shell overlay.
- Preserve `wallpapers/`: files are not referenced by the current DMS workflow,
  but are user assets and deletion is not justified by lack of references.
- Add app rules for Kitty, Obsidian, and Nautilus. OpenCode is a terminal TUI
  and inherits Kitty's Niri window rule when run inside Kitty; it does not have
  a separate compositor app-id in that case.
- OpenCode currently has no repository-owned configuration. Its existing
  `~/.config/opencode/service.json` is user-owned and is not modified. The
  OpenCode right-sidebar layout is therefore not changed by this phase.

## Deployment

`scripts/link-configs.sh` links managed files into `$XDG_CONFIG_HOME` (default
`~/.config`), preserving generated and unrelated files in those directories.
Existing regular files at managed paths are renamed to
`*.before-dotfiles-link`; if such a backup already exists, the script stops.

## Implementation and validation

- Moved the GTK, Kitty, Matugen, Niri, and systemd configuration trees under
  `.config/`; updated the active Matugen test paths and architecture link.
- Added GTK3/GTK4 user CSS that imports DMS-generated colors and derives
  translucent surface colors from the generated semantic GTK colors.
- Added Niri floating rules for Kitty, Obsidian, and Nautilus, including width
  defaults and 12px clipping. The CLI OpenCode session inherits the Kitty
  window rule when launched inside Kitty.
- Added `scripts/link-configs.sh`. It was tested against a temporary
  `XDG_CONFIG_HOME`, including preservation of an existing settings file.
- `niri validate -c .config/niri/config.kdl`: passed on Niri 26.04.
- `bash -n scripts/link-configs.sh`: passed.
- `python3 -B -m unittest discover -s tests/theme -p 'test_dynamic_theme.py' -v`:
  9 tests passed.
- `python3 -B -m unittest discover -s tests/cursor -v`: 14 tests passed.
- `node --test tests/layout/*.test.js`: 1,803 tests passed.
- Full theme suite: 20 passed, 1 error and 1 failure. The error references
  the absent `hypr/.config/hypr/modules/theme_tokens.lua`; the failure expects
  a DMS-bundled font at `/usr/share/quickshell/dms/DankCommon/assets/fonts`,
  which is absent in this environment. Neither relates to the migrated
  Matugen paths.
- `git diff --check`: passed.

GTK CSS could not be exercised visually here; GTK demo binaries are absent.
The Niri interactive floating behavior and live GTK transparency still need
desktop verification. The OpenCode sidebar has no repository-owned config in
this checkout; its existing service configuration remains untouched, and
sidebar removal is not claimed as implemented.

## Apply

After reviewing existing runtime files and their backups, run:

```bash
cd ~/Documents/projects/dotfiles
scripts/link-configs.sh
niri msg action load-config-file
```

The installer links versioned files into `~/.config` and preserves regular
files it replaces as `.before-dotfiles-link`. It does not enable the systemd
cursor units or alter OpenCode.

On the inspected machine, the active Niri `config.kdl` includes
`dms/windowrules.kdl`, a DMS-generated file not present in the repository.
Merge/preserve that include before replacing the active config; the automated
installer intentionally does not resolve configuration-level merge conflicts.
