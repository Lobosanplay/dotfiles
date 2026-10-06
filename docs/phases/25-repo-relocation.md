# Phase 25 — Repository Relocation

## Status

Completed. The repository moved from `~/dotfiles` to
`~/Documents/projects/dotfiles`; every link and hardcoded path that depended
on the old location now points at the new one. No packages, drivers, or
Hyprland modules were changed.

## Problem

After the move, the dotfiles stopped applying because the old path no longer
existed:

| Integration | Mechanism | Effect of the move |
| --- | --- | --- |
| `~/.config/matugen` | Absolute symlink into the repo | Broken; DMS could not run the project's Matugen template. |
| `~/.config/kitty/dotfiles-theme.conf` | Absolute symlink into the repo | Broken; `include dotfiles-theme.conf` in `kitty.conf` loaded nothing. |
| `dms.service.d/overlay.conf` | `ExecStart` calls `$HOME/dotfiles/scripts/dms-overlay.sh` | On the next DMS start the overlay would not build and DMS would fall back to the stock UI (no WorkspaceGraph overview overrides). |
| Matugen `post_hook` | Calls `$HOME/dotfiles/scripts/promote_dynamic_theme.py` | Dynamic colors would no longer be promoted to Hyprland. |

Not affected: the active Hyprland config, GTK settings, and the DMS overlay
tree are regular copies (see Phase 24), and the overlay copies its overrides
instead of linking them.

## Changes

Repository:

- `systemd/.config/systemd/user/dms.service.d/overlay.conf`: script path.
- `matugen/.config/matugen/config.toml`: `post_hook` script path.
- `docs/architecture/wallpaper-theme.md`: documented `ln -s` command.

Machine (not versioned):

- `ln -sfn` repointed `~/.config/matugen` and
  `~/.config/kitty/dotfiles-theme.conf` to the new location.
- Copied the updated drop-in to `~/.config/systemd/user/dms.service.d/` (the
  previous copy is kept as `overlay.conf.before-relocation`, which systemd does
  not load) and ran `systemctl --user daemon-reload`.

## Validation

- Both symlinks resolve (`readlink -e`); no broken links remain under
  `~/.config/matugen` or `~/.config/kitty`.
- `systemctl --user cat dms.service` shows the new `ExecStart`;
  `NeedDaemonReload=no`.
- `dms-overlay.sh --check` from the new path: DMS 1.6.2, all overrides match,
  exit 0.
- `promote_dynamic_theme.py --help` runs; Kitty parses `kitty.conf`.
- Layout tests (`node tests/layout/*.test.js`) pass; theme tests
  (`python3 -m unittest discover -s tests/theme`) 22 OK.
- `git diff --check` clean.

DMS was not restarted in this phase; the new `ExecStart` takes effect on the
next DMS restart or login. A dynamic-theme run through DMS was not triggered.

## Known limitations

Paths remain absolute. Moving the repository again requires repeating these
steps; a location-independent approach (e.g. resolving the repo from the
symlink target) is possible future work.
