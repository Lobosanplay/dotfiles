# Phase 29 — Niri Workspace Foundation

## Status

**Complete**

## Objective

Introduce Niri as a second Wayland compositor/session on Fedora 44 and establish a native Niri workspace model based on named workspaces, native navigation, keybindings and Niri's built-in Overview.

This phase intentionally establishes the architectural foundation only.

The existing Hyprland workspace architecture remains fully intact and operational.

Niri is authoritative for workspace management only inside the Niri session.

---

# 1. Context

The current desktop environment is based on:

* Fedora 44
* Wayland
* Hyprland
* DMS / Quickshell
* a custom Lua `WorkspaceGraph`
* persistent workspace graph state
* persistent workspace metadata
* DMS workspace overview overrides

The existing Hyprland workspace system remains unchanged.

Its architecture is approximately:

```text
Hyprland
    │
    ├── WorkspaceGraph
    │      ├── directional connections
    │      ├── workspace creation
    │      ├── workspace removal
    │      ├── navigation
    │      └── persistence
    │
    ├── WorkspaceMetadata
    │
    └── keybinds
             │
             ▼
      DMS / Quickshell
             │
             └── custom Workspace Overview
```

The graph persists to:

```text
~/.local/state/hyprland/workspace-graph.json
```

Workspace metadata persists separately:

```text
~/.local/state/hyprland/workspace-metadata.json
```

These systems were not modified by Phase 29.

---

# 2. Architectural Decision

## Option B — Independent Niri workspace architecture

**Implemented and validated.**

Niri does not attempt to emulate the existing Hyprland `WorkspaceGraph`.

Instead:

```text
Hyprland session
    │
    └── WorkspaceGraph
         └── DMS custom Overview


Niri session
    │
    ├── Native Niri workspaces
    ├── Named workspaces
    ├── Native navigation
    ├── Niri keybindings
    └── Native Niri Overview
```

Each compositor owns its own workspace model.

This avoids creating a compatibility layer between two fundamentally different workspace systems.

### Rationale

Niri's workspace model is not a four-direction graph.

The implemented abstraction is therefore:

```text
Hyprland:
workspace ID → directional graph

Niri:
workspace name → semantic destination
```

No compatibility graph or synchronization layer was introduced.

---

# 3. Goals

Phase 29 established:

1. Niri installed on Fedora 44.
2. A functional Niri Wayland session.
3. Niri available independently from Hyprland through GDM.
4. A version-controlled Niri configuration.
5. A modular configuration structure.
6. Named workspaces.
7. Workspace navigation.
8. Workspace-to-window movement bindings.
9. Native Niri Overview.
10. DMS compatibility sufficient to operate the Niri session without a duplicate bar.
11. A documented rollback procedure.
12. Validation commands and acceptance criteria.

### Implementation note

Minimal application-specific window rules were **not** added in this phase.

The real Niri application identifiers were inspected for future use:

```text
Brave     → brave-browser
Vesktop   → vesktop
Zed       → dev.zed.Zed
```

They remain available for a future application-placement phase.

---

# 4. Explicit Non-Goals

## 4.1 No Hyprland removal

No Hyprland workspace infrastructure was removed or rewritten.

The following remain intact:

```text
hypr/
WorkspaceGraph
WorkspaceMetadata
workspace-graph.json handling
workspace-metadata.json handling
Hyprland workspace keybindings
```

---

## 4.2 No DMS workspace migration

The existing Hyprland DMS Overview was not migrated or replaced.

Niri uses its native Overview.

DMS itself remains active in the Niri session, but Phase 29 does not attempt to redesign or migrate the DMS shell.

---

## 4.3 No broad application migration

No application ecosystem was ported from another dotfiles repository.

No launchers, terminals, browsers, file managers, notification systems, wallpaper systems or other third-party desktop configuration were migrated as part of this phase.

---

## 4.4 No theme migration

The existing theme infrastructure remains untouched.

No migration was performed for:

```text
theme_tokens.lua
DMS theme
Matugen integration
GTK theme
Kitty theme
cursor system
```

---

## 4.5 No NVIDIA optimization

No NVIDIA, PRIME, driver or GPU configuration was modified.

NVIDIA remained operational throughout testing.

---

## 4.6 Niri does not become the default compositor

Hyprland remains independently selectable through GDM.

No default GDM session was changed.

---

# 5. Niri Configuration Architecture

The repository now contains:

```text
dotfiles/
├── niri/
│   └── .config/
│       └── niri/
│           ├── config.kdl
│           ├── workspaces.kdl
│           └── binds.kdl
│
└── docs/
    └── phases/
        └── 29-niri-workspace-foundation.md
```

The configuration uses Niri's native `include` mechanism.

`config.kdl` contains the version-compatible Fedora Niri baseline and includes:

```text
workspaces.kdl
binds.kdl
```

The configuration remains intentionally close to the Fedora-provided default configuration rather than replacing it with a minimal third-party configuration.

A separate `rules.kdl` was **not** introduced because no application-placement rules were necessary to establish the workspace foundation.

---

# 6. Workspace Model

## 6.1 Principle

Niri uses semantic workspaces rather than reproducing the numeric/directional graph used by Hyprland.

The implemented workspace set is:

```text
main
code
browser
communication
media
gaming
```

These names are semantic destinations rather than permanent physical monitor positions.

---

# 7. Workspace Semantics

## `main`

General-purpose workspace.

Neutral/default destination for miscellaneous applications and temporary tasks.

---

## `code`

Development workspace.

Intended for:

* code editors
* terminals
* development tools
* project-related windows

---

## `browser`

General web browsing and research.

Intended for browsers, documentation and web applications.

---

## `communication`

Communication-oriented applications.

Potentially used by Discord, messaging and collaboration applications.

No application-specific placement rule was introduced in this phase.

---

## `media`

Media consumption.

Potentially used by Spotify and media applications.

No application-specific placement rule was introduced in this phase.

---

## `gaming`

Games and gaming-related windows.

The workspace exists as a semantic destination without additional gaming-specific rules.

---

# 8. Why Named Workspaces

Named workspaces were selected because they provide stable semantic destinations without coupling configuration to dynamic numeric workspace indices.

The implemented bindings reference workspace names directly:

```text
focus-workspace "main"
focus-workspace "code"
focus-workspace "browser"
focus-workspace "communication"
focus-workspace "media"
focus-workspace "gaming"
```

Window movement uses the corresponding named workspace actions.

This keeps workspace identity independent of the numeric ordering reported by Niri.

---

# 9. Workspace Ordering

The declared order is:

```text
main
code
browser
communication
media
gaming
```

This represents the initial semantic ordering.

It is not treated as an immutable physical workspace graph.

During validation, Niri associated the declared named workspaces with `eDP-1` while `HDMI-A-2` maintained its own dynamic workspace sequence.

This behavior was accepted rather than overridden with explicit `open-on-output` rules.

No monitor-specific workspace policy was hard-coded during Phase 29.

---

# 10. Workspace Navigation

The implemented semantic bindings are:

```text
Super + 1 → main
Super + 2 → code
Super + 3 → browser
Super + 4 → communication
Super + 5 → media
Super + 6 → gaming
```

The configuration was validated successfully by Niri.

The numeric default bindings for the same workspace range were removed from the copied Fedora default configuration to avoid conflicting behavior.

---

# 11. Relative Navigation

Niri's native workspace navigation remains available.

The configuration retains native Niri actions such as:

```text
focus-workspace-up
focus-workspace-down
focus-workspace-left
focus-workspace-right
```

where provided by the default configuration.

No custom workspace graph layer was introduced.

---

# 12. Window Movement

The semantic workspace bindings also provide movement of the focused column:

```text
Super + Ctrl + 1 → main
Super + Ctrl + 2 → code
Super + Ctrl + 3 → browser
Super + Ctrl + 4 → communication
Super + Ctrl + 5 → media
Super + Ctrl + 6 → gaming
```

The conceptual model is therefore:

```text
focus workspace
        │
        └── named destination

move focused column
        │
        └── named destination
```

No graph state or compatibility state is involved.

---

# 13. Native Overview

Niri's native Overview remains enabled.

The Fedora default configuration's native Overview binding was preserved.

The implemented configuration therefore does **not** replace Niri Overview with the Hyprland DMS graph Overview.

This maintains the architectural separation:

```text
Hyprland:
Super + Tab → existing DMS Overview

Niri:
native Niri Overview
```

The native Niri Overview was retained as the appropriate workspace visualization for this session.

---

# 14. Window Rules

No `rules.kdl` was introduced.

The phase deliberately stopped before automatic application placement.

Real Niri application identifiers were inspected during testing:

```text
Spotify     → spotify
Vesktop     → vesktop
Brave       → brave-browser
Zed         → dev.zed.Zed
```

These identifiers provide a verified basis for a future application-placement phase.

No speculative rules were added.

---

# 15. Rule Design Principle

The rule strategy for future phases remains:

```text
specific application
        ↓
specific workspace
```

rather than broad categories such as:

```text
all GTK applications
all Qt applications
all terminals
all browsers
```

This phase intentionally leaves those rules for later.

---

# 16. Monitor Behavior

The physical monitor configuration was inspected inside Niri before introducing output-specific workspace rules.

Niri reported:

```text
eDP-1
1920x1200 @ 180 Hz
position 0,0
scale 1

HDMI-A-2
1600x900 @ 60 Hz
position 1920,0
scale 1
```

No `open-on-output` rules were added.

The reason is intentional: workspace semantics were established first, while persistent monitor/workspace policy remains a future concern.

---

# 17. Installation Strategy

Niri was installed using Fedora's packaged Niri implementation.

The available Fedora Updates package was:

```text
niri-26.04-1.fc44.x86_64
```

The installed version is:

```text
niri 26.04
```

The installation was performed through Fedora's package manager rather than manual compilation.

No Arch/AUR installation mechanism was introduced.

The transaction installed Niri and its Fedora package dependencies/weak dependencies without removing existing desktop components.

---

# 18. Session Integration

GDM now exposes Niri as a separate Wayland session.

The installed session descriptor is:

```text
/usr/share/wayland-sessions/niri.desktop
```

Its relevant contents are:

```ini
[Desktop Entry]
Name=Niri
Comment=A scrollable-tiling Wayland compositor
Exec=niri-session
Type=Application
DesktopNames=niri
```

The resulting session structure is:

```text
GDM
 ├── Hyprland
 ├── Hyprland (UWSM)
 ├── GNOME
 ├── GNOME Classic
 └── Niri
```

No manual modification of the system session descriptor was required.

---

# 19. Repository Deployment

The repository does not use a universal GNU Stow deployment model.

Phase 29 therefore did not introduce Stow.

The canonical repository configuration is:

```text
niri/.config/niri/
```

The active configuration was kept synchronized with the repository configuration during validation.

The following files were verified byte-for-byte identical between the active configuration and repository:

```text
config.kdl
workspaces.kdl
binds.kdl
```

SHA-256 verification produced matching hashes for each corresponding pair.

---

# 20. Default Configuration Baseline

The configuration began from the Fedora-provided Niri 26.04 default configuration.

This preserved:

* current KDL syntax
* native Niri defaults
* current input configuration
* layout defaults
* native Overview
* animations
* screenshot configuration
* native keybindings
* current Niri-compatible options

Only the workspace and keybinding portions required for Phase 29 were customized.

The Niri version used throughout validation was:

```text
niri 26.04
```

---

# 21. Interaction With DMS

DMS was tested in the Niri session.

The DMS service remained active:

```text
/usr/bin/dms run --session
```

and its Quickshell overlay was running.

An initial duplicate-bar condition was identified.

The cause was the Fedora Niri default example:

```text
spawn-at-startup "waybar"
```

This was removed from the repository-managed Niri configuration.

It was replaced with a comment documenting that DMS provides the session bar.

After relogin:

```text
Waybar → not running
DMS → active
```

This eliminated the duplicate-bar condition without modifying DMS itself.

Therefore the final Phase 29 architecture is:

```text
Niri
  │
  └── DMS session shell
          │
          └── no Waybar duplicate
```

DMS workspace/visual integration beyond this compatibility correction remains outside the scope of Phase 29.

---

# 22. Hyprland Compatibility

Hyprland remained untouched by the Niri implementation.

No changes were made to:

```text
hypr/.config/hypr/
dms/overrides/Modules/WorkspaceOverlays/
tests/layout/
```

The final Git scope confirms that the implementation consists exclusively of Niri configuration files.

The existing Hyprland workspace architecture remains available independently.

---

# 23. State Isolation

Niri does not use the Hyprland workspace state files:

```text
~/.local/state/hyprland/workspace-graph.json
~/.local/state/hyprland/workspace-metadata.json
```

No compatibility state file was introduced.

The resulting separation remains:

```text
Hyprland
    └── WorkspaceGraph
          └── ~/.local/state/hyprland/


Niri
    └── native named workspace state
```

The two workspace systems remain independent.

---

# 24. Final Repository Changes

The Phase 29 implementation adds:

```text
niri/
└── .config/
    └── niri/
        ├── config.kdl
        ├── workspaces.kdl
        └── binds.kdl
```

The configuration contains:

* Fedora Niri 26.04 baseline
* DMS-compatible bar startup behavior
* named workspaces
* semantic workspace bindings
* semantic column-movement bindings
* previous-workspace navigation

No `rules.kdl` was added because application-placement rules were intentionally deferred.

---

# 25. Files Explicitly Not Modified

The following remained outside the Phase 29 change set:

```text
hypr/.config/hypr/hyprland.lua

hypr/.config/hypr/modules/workspaces.lua

hypr/.config/hypr/modules/workspace_metadata.lua

hypr/.config/hypr/modules/keybinds.lua

hypr/.config/hypr/modules/dms.lua

dms/overrides/Modules/WorkspaceOverlays/

tests/layout/
```

The custom `GraphLayout.js` was not converted into a Niri workspace layout engine.

---

# 26. Implementation Sequence

## Step 1 — Preflight

**Complete.**

Repository state, branch, Hyprland architecture and current session were inspected before modification.

---

## Step 2 — Inspect Niri packaging

**Complete.**

Fedora package availability and the Niri package contents were inspected before installation.

The Fedora Updates package was identified as:

```text
niri-26.04-1.fc44
```

The package contents confirmed:

* `/usr/bin/niri`
* `/usr/bin/niri-session`
* Niri systemd user integration
* GDM/Wayland session integration
* Fedora Niri portal configuration
* version-compatible default configuration

---

## Step 3 — Install Niri

**Complete.**

Niri was installed through Fedora packaging.

Verified:

```text
command -v niri
→ /usr/bin/niri

command -v niri-session
→ /usr/bin/niri-session

niri --version
→ niri 26.04
```

---

## Step 4 — Verify GDM session

**Complete.**

GDM exposes:

```text
niri.desktop
```

and `niri-session` starts successfully.

---

## Step 5 — Create repository configuration

**Complete.**

The Fedora Niri 26.04 default configuration was copied into:

```text
niri/.config/niri/config.kdl
```

and modularized with:

```text
workspaces.kdl
binds.kdl
```

---

## Step 6 — Establish named workspaces

**Complete.**

The following named workspaces were added:

```text
main
code
browser
communication
media
gaming
```

`niri validate` succeeds.

---

## Step 7 — Add workspace bindings

**Complete.**

Semantic focus bindings were added:

```text
Super + 1..6
```

Semantic column movement bindings were added:

```text
Super + Ctrl + 1..6
```

Previous-workspace navigation was added:

```text
Super + Tab
```

with repeat disabled.

Native Niri navigation and Overview behavior remain available.

---

## Step 8 — Add minimal window rules

**Deferred intentionally.**

Real application identifiers were verified, but no automatic placement rules were necessary to prove the workspace foundation.

This work belongs in a future application-placement phase.

---

## Step 9 — Start Niri

**Complete.**

Niri was started from GDM and validated as a functioning Wayland session.

Verified:

```text
XDG_SESSION_TYPE=wayland
XDG_CURRENT_DESKTOP=niri
XDG_SESSION_DESKTOP=niri
WAYLAND_DISPLAY=wayland-1
```

---

# 27. Validation Matrix

## Installation

**PASS**

```text
niri --version
```

Result:

```text
niri 26.04
```

---

## Configuration

**PASS**

```text
niri validate -c ~/.config/niri/config.kdl
```

Result:

```text
INFO niri: config is valid
```

The repository configuration was also validated successfully.

---

## Session

**PASS**

```text
XDG_SESSION_TYPE=wayland
XDG_CURRENT_DESKTOP=niri
XDG_SESSION_DESKTOP=niri
```

Niri service:

```text
niri.service → active
```

---

## Outputs

**PASS**

Niri detects:

```text
eDP-1
1920x1200 @ 180.001 Hz

HDMI-A-2
1600x900 @ 60 Hz
```

No explicit workspace/output policy was required.

---

## Workspaces

**PASS**

Niri reported the declared semantic workspaces:

```text
1 "main"
2 "code"
3 "browser"
4 "communication"
5 "media"
6 "gaming"
```

The workspaces were observed as persistent named destinations.

Additional dynamic workspace IDs may exist independently of these named workspaces.

---

## Navigation

**PASS**

The semantic workspace bindings were incorporated into the active configuration and workspace state was observed changing between the named destinations.

---

## Window movement

**CONFIGURATION PASS**

The semantic movement bindings are implemented using Niri's native:

```text
move-column-to-workspace
```

actions.

Automatic application-placement rules were intentionally not introduced.

---

## Previous workspace

**PASS**

The configuration includes:

```text
Mod+Tab repeat=false {
    focus-workspace-previous;
}
```

---

## Overview

**PASS**

Niri's native Overview remains enabled through the Fedora default configuration.

No custom DMS workspace Overview was introduced into the Niri configuration.

---

## DMS / Waybar

**PASS**

After removing the default Waybar startup example:

```text
Waybar → not running
DMS → active
```

The duplicate-bar condition was resolved.

---

## Repository synchronization

**PASS**

Active and repository configuration files were verified with `cmp` and SHA-256 hashes.

Verified identical:

```text
config.kdl
workspaces.kdl
binds.kdl
```

---

## Hyprland scope

**PASS**

Git inspection confirmed no changes under:

```text
hypr/
dms/
```

The Phase 29 implementation remains isolated to:

```text
niri/
```

plus its documentation.

---

## NVIDIA

**PASS**

NVIDIA remained operational:

```text
GeForce RTX 3050 6GB Laptop GPU
Driver 615.71.09
```

No NVIDIA configuration changes were required.

---

## Git validation

**PASS**

```text
git diff --check
```

completed without errors.

The final repository working tree contains only the three intended Niri configuration files before documentation/commit completion:

```text
A niri/.config/niri/binds.kdl
A niri/.config/niri/config.kdl
A niri/.config/niri/workspaces.kdl
```

The temporary repository backup was removed from the repository and moved outside it.

---

# 28. Failure Boundaries

The following boundaries were maintained during implementation.

### Niri startup

Niri startup was investigated independently from Hyprland.

No Hyprland configuration changes were required.

### Workspace behavior

Workspace behavior was implemented exclusively through Niri configuration.

No compatibility graph was created.

### DMS

The duplicate-bar issue was isolated to Niri's default Waybar autostart.

The fix removed only that Niri startup entry.

DMS itself was not modified.

### NVIDIA

No GPU changes were introduced to solve desktop/session behavior.

---

# 29. Rollback

Phase 29 remains reversible.

Rollback consists of:

1. Select Hyprland from GDM.
2. Verify Hyprland remains functional.
3. Remove or disable the Niri session if required.
4. Remove the repository/deployed Niri configuration.
5. Remove Niri packages if they are no longer required.
6. Leave all Hyprland and DMS files untouched.

Because the Hyprland workspace architecture was not modified, rollback does not require restoration of Hyprland workspace files.

Backups created during implementation were preserved outside the repository.

---

# 30. Security and System Integrity

No prohibited system-integrity shortcuts were used.

Phase 29 did not:

* manually modify `/usr/share` session files;
* disable SELinux;
* disable security services;
* modify NVIDIA drivers;
* replace global portal configuration unnecessarily;
* introduce Arch/AUR installation commands;
* overwrite unrelated system configuration.

Niri was installed using Fedora packaging.

---

# 31. Documentation Requirements

The implementation records the following:

### Niri version

```text
26.04
```

### Fedora package

```text
niri-26.04-1.fc44.x86_64
```

### Session integration

```text
/usr/share/wayland-sessions/niri.desktop
```

using:

```text
Exec=niri-session
```

### Configuration

```text
~/.config/niri/config.kdl
```

Repository source:

```text
niri/.config/niri/config.kdl
```

### Workspace names

```text
main
code
browser
communication
media
gaming
```

### Binding decisions

```text
Super + 1..6
Super + Ctrl + 1..6
Super + Tab
```

### Window-rule decision

No automatic application-placement rules in Phase 29.

Verified identifiers were recorded for future work.

### Known limitation

Named workspaces were observed on `eDP-1`, while `HDMI-A-2` maintained its own dynamic workspace sequence.

No hard-coded output policy was introduced.

A dedicated multi-monitor workspace policy remains a future phase.

---

# 32. Commit Boundary

Before the final implementation commit, the following were reviewed:

```text
git status
git diff
git diff --check
```

The final implementation scope is limited to:

```text
niri/.config/niri/config.kdl
niri/.config/niri/workspaces.kdl
niri/.config/niri/binds.kdl
docs/phases/29-niri-workspace-foundation.md
```

The intended commit remains:

```text
feat(niri): add workspace foundation
```

No push is performed automatically.

---

# 33. Acceptance Criteria

* [x] Niri is installed through a Fedora-compatible method.
* [x] Niri appears as a selectable GDM session.
* [x] Hyprland remains selectable.
* [x] Niri starts successfully.
* [x] Niri configuration is stored in the dotfiles repository.
* [x] `niri validate` succeeds.
* [x] Named workspaces are defined.
* [x] Workspace navigation is configured and validated.
* [x] Window movement between workspaces is configured using native Niri actions.
* [x] Native Overview is preserved and available.
* [x] Minimal window rules were intentionally deferred; no speculative rules were introduced.
* [x] No Hyprland WorkspaceGraph files were removed.
* [x] No DMS workspace overrides were removed.
* [x] No broad application migration was performed.
* [x] No theme migration was performed.
* [x] No NVIDIA optimization was performed.
* [x] Niri/DMS integration was validated without a duplicate Waybar.
* [x] Hyprland configuration remained outside the Phase 29 diff.
* [x] `git diff --check` passes.
* [x] Final implementation diff contains only Phase 29 changes.
* [x] Rollback path is documented.

---

# 34. Future Phases

The following remain candidates for later phases.

### Niri desktop integration

Potentially:

```text
DMS
launcher
notifications
wallpaper
lock screen
system controls
```

The DMS session itself already operates under Niri, but deeper Niri-specific integration remains separate work.

### Niri visual integration

Potentially:

```text
Graphite/Slate
cursor
fonts
borders
animations
gaps
theme tokens
```

### Application placement

Potentially:

```text
browser → browser
editor → code
Discord → communication
Spotify → media
Steam/games → gaming
```

Verified application IDs are available for implementing these rules safely.

### Multi-monitor workspace policy

Potentially:

```text
workspace → output
```

after determining the desired persistent monitor/workspace policy.

### Niri-specific automation

Only after the base configuration remains stable.

---

# 35. Architectural Summary

The final Phase 29 architecture is:

```text
                    Fedora 44
                       │
                       ▼
                      GDM
                   ┌───┴───┐
                   │       │
                   ▼       ▼
               Hyprland   Niri
                   │       │
                   │       ├── named workspaces
                   │       ├── native navigation
                   │       ├── native window movement
                   │       └── native Overview
                   │
                   ├── WorkspaceGraph
                   ├── WorkspaceMetadata
                   └── DMS custom Overview
```

DMS remains available as the session shell under Niri without introducing a second Waybar.

The key architectural boundary remains:

```text
Hyprland workspace state ≠ Niri workspace state
```

Niri uses Niri's own primitives instead of carrying forward an abstraction designed specifically for Hyprland.

This keeps the migration reversible, avoids duplicate workspace state, and leaves the existing Hyprland environment untouched.

---

# 36. Final Decision

Phase 29 adopts and successfully implements **Option B: independent Niri workspace architecture**.

The initial Niri workspace model is:

```text
main
code
browser
communication
media
gaming
```

with semantic navigation, native column movement and Niri's native Overview.

The final implementation proves that Niri can operate as an independent Wayland session alongside the existing Hyprland environment.

No custom workspace graph was introduced for Niri.

No existing Hyprland workspace infrastructure was removed.

No broad application or desktop-shell migration was performed.

The phase therefore achieves its intended milestone:

```text
"prove that Niri can provide a clean, stable, semantic workspace environment
alongside the existing Hyprland environment."
```

## Phase 29 result

**COMPLETE**

The remaining work belongs to subsequent phases, particularly application placement, multi-monitor workspace policy, and deeper Niri/DMS/visual integration.
