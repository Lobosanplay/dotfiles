# Phase 24 — Portability, Reproducibility & System Health

## Status

Audit completed with a small cursor-persistence fix. Steam/game failure and
post-login cursor appearance remain unconfirmed and are recorded as open
items. No packages were installed, no driver was changed, and no reboot was
performed.

## Baseline

- Fedora Linux 44; kernel `7.2.8-200.fc44.x86_64`.
- Hyprland `0.56.2`; DMS `1.6.2`; Quickshell `0.3.1`; Matugen `4.2.0`.
- Intel Raptor Lake-P integrated GPU plus NVIDIA GeForce RTX 3050 Laptop GPU.
- Initial branch `main`, starting commit `d7e9f6d`; clean working tree and two
  commits ahead of `origin/main`.
- DMS user service is active. No failed user units were reported.
- Hyprland `configerrors` was empty before and after the change.

## Drivers, NVIDIA, PRIME, and Vulkan

| Area | Evidence and result |
| --- | --- |
| Intel | `i915` bound to the Intel Raptor Lake-P GPU. Normal `glxinfo -B` reports Mesa Intel Graphics and accelerated rendering. |
| NVIDIA | RTX 3050 Laptop GPU bound to `nvidia`; loaded module and userspace packages are version `615.71.09`. `nvidia-smi` succeeds and reports the card at 51 °C during inspection. |
| Module warning | Kernel reports an unsigned/out-of-tree NVIDIA module signature and taints the kernel. The module is loaded and operational; this is a warning, not evidence of a failed driver. |
| PRIME | Offload `glxinfo -B` with `__NV_PRIME_RENDER_OFFLOAD=1` and `__GLX_VENDOR_LIBRARY_NAME=nvidia` selects the RTX 3050 successfully. `~/.local/bin/nvidia-run` sets the expected offload variables and then executes the requested command. |
| Vulkan | `vulkaninfo --summary` enumerates Intel, NVIDIA, and llvmpipe. Vulkan loader, Mesa Vulkan, and NVIDIA libraries are installed for both x86_64 and i686. A DZN ICD is skipped and display-plane extension warnings appear; no observed NVIDIA Xid or Vulkan NVIDIA failure accompanied them. |

**Conclusion:** Intel rendering, NVIDIA driver loading, PRIME OpenGL offload, and
NVIDIA Vulkan enumeration are functional. The desktop is using both GPUs as
intended. No driver change is indicated by this audit.

## Steam and games

- Fedora package `steam-1.0.0.87-1.fc44.x86_64` is installed. Steam is not
  running now. 32-bit glibc, Vulkan loader, Mesa Vulkan, and NVIDIA userspace
  libraries are present.
- Existing Steam logs show Detroit: Become Human (AppID `1222140`) launched
  with Proton Hotfix on October 3, 2026; Steam recorded the game process
  exiting about three seconds later. No game-specific Proton/DXVK log was
  found, so the failing layer and GPU selection are **unconfirmed**.
- Existing client logs also contain Steam network/connectivity failures and
  webhelper/CEF warnings. These do not identify the reported game's cause.
- `nvidia-smi` did not show a running game during this audit. No reproducible
  game launch was performed, so no Steam/Proton/GPU correction is justified.
- **Diagnostic caveat:** `steam --version` is not a harmless version query for
  this launcher; the audit invocation started Steam inside the restricted
  command sandbox and it terminated with `SIGSYS`. This produced a 93.4 KiB
  system coredump for the audit command. It is not evidence of the user's
  normal Steam/game failure. The coredump was not deleted.

## Cursor

### Observed state

- DMS persists `theme=Frieren-Winter`, `size=59` in
  `~/.config/DankMaterialShell/settings.json`.
- The theme files exist in `~/.icons/Frieren-Winter`; this is a per-user,
  machine-local installation and is not versioned.
- GSettings reports cursor theme `Frieren-Winter` and size `59`. GTK3/GTK4
  `settings.ini` files currently set icon theme and dark preference only; they
  do not define cursor values.
- The actual systemd user-manager environment before a new login has
  `XCURSOR_SIZE=24`, `HYPRCURSOR_SIZE=24`, and no cursor theme variables. The
  shell executing this audit reported size 61; this differs from the user
  manager and is not treated as the desktop session's source of truth.
- Brave is native Wayland on `eDP-1` scale 1.5. ChatGPT is XWayland on
  `HDMI-A-2` scale 1.0. Different backend and monitor scale are confirmed;
  their individual contribution to the perceived size difference cannot be
  measured from this audit alone.

### Confirmed persistence cause and correction

DMS writes persisted cursor values to `~/.config/hypr/dms/cursor.lua` and its
generated `hyprland.lua.dms` includes `require("dms.cursor")`. The active
project configuration did not load that generated cursor module; it declared
size 24 later in `hyprland.lua`, overriding earlier module values. Therefore
the on-disk DMS selection existed, but was not reliably part of the active
startup configuration.

The versioned and active configurations now set size 24 defaults before
loading modules, and `modules/dms.lua` optionally loads `dms.cursor`. This
keeps a clean-install fallback while allowing DMS's saved theme and size to
override it. The active files were backed up as
`~/.config/hypr/hyprland.lua.before-phase24` and
`~/.config/hypr/modules/dms.lua.before-phase24`; earlier backups were left
untouched.

The config reloaded cleanly. The systemd manager still reported the previous
24 values during this already-running login; the existing startup hook copies
the compositor environment to systemd on a new Hyprland start. A logout/login
or reboot test was not performed, so post-login application appearance remains
to be verified. No cursor-specific GTK/XWayland workaround was added.

## Dependencies

| Component | Status | Required by project | Evidence |
| --- | --- | --- | --- |
| `hyprland`, `hyprctl` | Present | Required | Active compositor and theme/overview/overlay integration. |
| `quickshell`, `dms` | Present | Required | DMS shell and user service; DMS service is active. |
| `kitty` | Present | Required | Terminal keybind and tracked Kitty theme integration. |
| `matugen` | Present | Required for dynamic wallpaper theme | Tracked Matugen template and DMS post-hook. |
| `wl-copy` | Present | Optional | Installed, but no active project script/config reference found. |
| `dolphin` | Missing | Required by current `SUPER+E` binding | `modules/keybinds.lua` executes `dolphin`. No package was installed. |
| `hyprlauncher` | Missing | Required by current `SUPER+R` binding | `modules/keybinds.lua` executes `hyprlauncher`. No package was installed. |
| `wlogout`, `waybar`, `rofi`, `awww`, `cliphist`, `starship` | Missing | Unused/optional for this configuration | No active project consumer found; old Waybar reference is commented out. |

The two missing commands are concrete portability gaps in existing shortcuts.
They were left unchanged because package provenance/availability and the user's
preferred replacement or installation route were not established in this
phase. They should be resolved in a narrowly scoped follow-up.

## Persistence, services, and theme runtime

- `dms.service` is active and invokes the repository's `scripts/dms-overlay.sh`
  before `dms run --session`. Overlay check reports installed DMS 1.6.2 and
  matching upstream fingerprints; the overlay is active.
- No failed user services were reported. The existing Hyprland startup hook
  starts `hyprland-session.target` and calls
  `dbus-update-activation-environment --systemd --all`.
- `SUPER+Y` remains mapped to `dms ipc call dash toggle wallpaper`; no wallpaper
  renderer or keybind was changed.
- Static colors come from the versioned theme contract and Graphite Slate
  component theme. Dynamic colors are generated by DMS's Matugen run using the
  tracked user template. `~/.local/state/hyprland/dynamic-colors.json` is the
  validated runtime result; `scripts/promote_dynamic_theme.py` generates
  `~/.config/hypr/dms/dotfiles_theme.lua` and applies validated Hyprland colors.
  DMS owns its GTK/Kitty outputs. The configured `~/.config/matugen` path is a
  symlink into the repository.
- DMS `settings.json`, Matugen state/lock, generated Hyprland DMS modules,
  GTK settings, and `~/.local/bin/nvidia-run` are local runtime or
  machine-specific files, not repository-managed sources.

## Portability and reproducibility inventory

| Class | Current examples |
| --- | --- |
| Versioned | Hyprland modules, theme contracts/templates, DMS overrides and preset, scripts, tests, and phase/architecture docs. |
| Generated | Dynamic semantic JSON, generated Hyprland theme/cursor Lua, DMS/Matugen GTK and Kitty output, DMS overlay symlink tree. |
| Machine-specific | Active monitor/output and DMS settings, installed cursor/icon themes, user-installed `nvidia-run`, external Steam library mount, and active Hyprland config copy. |
| Runtime state | Workspace graph/metadata JSON, Matugen lock/cache, DMS process/session, and compositor environment. |

Active Hyprland files are regular files, not symlinks. The active main config
also loads generated `dms.layout` and `dms.outputs`; its appearance module
contains an intentional local visual difference documented in Phase 23. The
active main config and repository therefore need explicit synchronization.
The active `modules/dms.lua` matched the repository before this phase and now
contains the same cursor integration change.

To reproduce this setup, a new machine needs Fedora-compatible packages for
the required commands above, DMS/Matugen, a user login/session, the user's
chosen cursor and icon themes, generated DMS settings and outputs, and the
repository symlinks/configuration described in the earlier phase docs. The
repo does not currently provide a complete machine bootstrap/package manifest.

## Validation

- `hyprctl configerrors`: empty before and after.
- `hyprctl reload`: returned `ok`.
- DMS service: active after reload; failed user units: none.
- `scripts/dms-overlay.sh --check`: passed against DMS 1.6.2.
- Theme tests: 22 passed across theme contract, dynamic theme, and DankBar
  preset suites.
- Layout tests: 2 passed; `node tests/layout/load-layout.js` exited 0.
- NVIDIA `nvidia-smi`, normal OpenGL, PRIME OpenGL, and Vulkan enumeration
  succeeded during the audit.
- No reboot, new login, or reproducible game launch was performed.
- `git diff --check`: passed before commit.

## Files changed

- `hypr/.config/hypr/hyprland.lua`
- `hypr/.config/hypr/modules/dms.lua`
- `docs/architecture/cursor.md`
- `docs/phases/24-system-health-and-portability.md`

## Follow-up

1. After the next logout/login, verify the cursor theme and size in native
   Wayland and XWayland apps on both outputs; update this document with the
   result.
2. Reproduce the Steam issue with the exact game, Proton version, launch
   options, and captured game/Proton log before changing GPU selection or
   installing anything.
3. Decide how to resolve the missing Dolphin and Hyprlauncher commands with
   Fedora-compatible package sources or alternate launchers.
4. Consider a package manifest/bootstrap process in a separate portability
   phase.
