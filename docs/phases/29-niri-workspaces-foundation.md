# Phase 29 — Niri Workspace Foundation

## Status

Planned

## Objective

Introduce Niri as a second Wayland compositor/session on Fedora 44 and establish a native Niri workspace model based on named workspaces, native navigation, keybindings and Niri's built-in Overview.

This phase intentionally establishes the architectural foundation only.

The existing Hyprland workspace architecture remains fully intact and operational throughout the phase.

Niri becomes authoritative for workspace management only inside the Niri session.

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

The current Hyprland workspace system is significantly customized.

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

This architecture is valid for Hyprland and should not be removed merely because Niri is being introduced.

---

# 2. Architectural Decision

## Option B — Independent Niri workspace architecture

Niri will not attempt to emulate the existing Hyprland `WorkspaceGraph`.

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
    ├── Native Niri navigation
    ├── Niri keybindings
    └── Native Niri Overview
```

Each compositor owns its own workspace model.

This avoids creating a compatibility layer between two fundamentally different workspace systems.

### Rationale

Niri's workspace model is not a four-direction graph.

Niri maintains independent workspace sequences per monitor, with dynamic workspaces arranged vertically. Named workspaces provide the persistent semantic layer needed for stable destinations.

Therefore the correct abstraction is:

```text
Hyprland:
workspace ID → directional graph

Niri:
workspace name → semantic destination
```

rather than:

```text
Hyprland graph
       ↓
Niri compatibility graph
       ↓
Niri workspaces
```

The second approach would duplicate state and create synchronization problems without providing a real benefit.

---

# 3. Goals

Phase 29 will establish:

1. Niri installed on Fedora 44.
2. A functional Niri Wayland session.
3. Niri available independently from Hyprland through GDM.
4. A version-controlled Niri configuration.
5. A modular configuration structure.
6. Named workspaces.
7. Workspace navigation.
8. Workspace-to-window movement.
9. Workspace-specific application placement where justified.
10. Native Niri Overview.
11. A minimal set of window rules required to test the workspace model.
12. A documented rollback procedure.
13. Validation commands and acceptance criteria.

---

# 4. Explicit Non-Goals

The following are explicitly outside Phase 29.

## 4.1 No Hyprland removal

Do not remove:

```text
hypr/
```

Do not remove or rewrite:

```text
WorkspaceGraph
WorkspaceMetadata
workspace-graph.json handling
workspace-metadata.json handling
Hyprland workspace keybindings
```

---

## 4.2 No DMS migration

Do not migrate DMS to Niri in this phase.

Do not remove:

```text
dms/overrides/
```

Do not replace the current DMS Overview.

Niri's native Overview will be used in the Niri session.

Niri already provides a native zoomed-out Overview capable of navigating workspaces and moving windows, so reproducing the current custom DMS graph Overview would be unnecessary at this stage.

---

## 4.3 No broad application migration

This phase does not select or install a complete application ecosystem from another dotfiles repository.

In particular, do not automatically port:

* launchers
* terminals
* browsers
* file managers
* notification daemons
* bars
* wallpaper systems
* audio utilities
* Bluetooth utilities
* custom shells
* theme systems
* miscellaneous scripts

Application selection and installation remain a separate future phase.

---

## 4.4 No theme migration

Do not migrate the existing Graphite/Slate theme system.

Do not rewrite:

```text
theme_tokens.lua
DMS theme
Matugen integration
GTK theme
Kitty theme
cursor system
```

The initial Niri session should prioritize functionality and workspace architecture.

---

## 4.5 No NVIDIA optimization

NVIDIA/PRIME configuration is not part of this phase.

Any rendering issue encountered while testing Niri should first be diagnosed independently rather than modifying the existing graphics configuration.

---

## 4.6 Niri does not become the default compositor

Hyprland remains the established session.

Niri is introduced as an additional selectable session.

No automatic GDM default-session change should be made.

---

# 5. Niri Configuration Architecture

Niri supports:

```text
~/.config/niri/config.kdl
```

and supports modular configuration through `include`.

Configuration changes are live-reloaded, and `niri validate` can parse the configuration without starting a session.

The repository should therefore use a structure similar to:

```text
dotfiles/
├── niri/
│   └── .config/
│       └── niri/
│           ├── config.kdl
│           └── ...
│
└── docs/
    └── phases/
        └── 29-niri-workspace-foundation.md
```

The exact subdivision of the Niri configuration should be decided during implementation after inspecting the current Niri default configuration.

Because Niri now supports `include`, modular files are preferred if the resulting structure remains understandable.

A possible future structure is:

```text
niri/
└── .config/
    └── niri/
        ├── config.kdl
        ├── workspaces.kdl
        ├── binds.kdl
        └── rules.kdl
```

This is a proposed implementation structure, not a requirement to blindly create every file.

The implementation phase must first inspect the current Niri default configuration and determine the smallest sensible decomposition.

---

# 6. Workspace Model

## 6.1 Principle

Niri should use semantic workspaces rather than reproducing the numeric/directional graph used by Hyprland.

The workspace names should describe their purpose.

Initial proposal:

```text
main
code
browser
communication
media
gaming
```

These names are intentionally semantic.

They are not intended to represent fixed physical positions.

---

# 7. Workspace Semantics

## `main`

General-purpose workspace.

Typical contents:

* temporary applications
* miscellaneous tasks
* applications that do not have a dedicated workspace

This should be the neutral/default destination.

---

## `code`

Development workspace.

Intended for:

* code editor
* terminal
* development tools
* project-related windows

The goal is to give development work a predictable semantic destination without requiring a numeric workspace number.

---

## `browser`

General web browsing and research.

Intended for:

* Brave
* documentation
* research
* web applications

---

## `communication`

Communication-oriented applications.

Potential examples:

* Discord
* messaging clients
* collaboration tools

Specific applications should not be installed or selected in Phase 29.

---

## `media`

Media consumption.

Potential examples:

* Spotify
* video players
* media-related applications

Again, application selection remains outside this phase.

---

## `gaming`

Games and gaming-related windows.

This workspace exists as a semantic destination but should not yet receive complex gaming-specific rules.

Gaming-specific behavior can be addressed later after the base Niri session is stable.

---

# 8. Why Named Workspaces

Niri named workspaces are persistent even when empty.

They can be referenced directly by name through actions such as:

```text
focus-workspace
move-column-to-workspace
```

and applications can be assigned to them through window rules.

This makes them a much better match for the desired semantic workspace model than trying to force Niri's dynamic numeric indices to behave like static Hyprland IDs.

Niri's numeric workspace indices are positional rather than permanent identifiers, so using names avoids coupling the configuration to workspace ordering.

---

# 9. Workspace Ordering

The initial workspace declaration order should be treated as a default presentation order rather than an immutable spatial layout.

Niri permits named workspaces to move between monitors and change position.

Therefore:

```text
main
code
browser
communication
media
gaming
```

represents the initial semantic set, not a permanent physical graph.

This is intentional.

---

# 10. Workspace Navigation

Navigation should be based on semantic destinations.

The first implementation should provide:

```text
Super + 1 → main
Super + 2 → code
Super + 3 → browser
Super + 4 → communication
Super + 5 → media
Super + 6 → gaming
```

These bindings are a proposed initial scheme.

Before implementation, they must be checked against:

* Niri default bindings
* existing personal habits
* keyboard layout
* conflicts with other controls

The actual key assignments should only be committed after that inspection.

---

# 11. Relative Navigation

Niri also provides native relative workspace navigation.

The implementation should preserve native actions such as:

```text
focus-workspace-up
focus-workspace-down
move-workspace-up
move-workspace-down
```

where appropriate.

These actions should not be wrapped in a custom graph layer.

Niri's workspace model is explicitly vertical per monitor, making native relative navigation more coherent than recreating directional graph semantics.

---

# 12. Window Movement

The workspace system should provide dedicated actions for moving the focused window/column to a semantic workspace.

The conceptual model is:

```text
focus workspace
move current column to workspace
```

rather than:

```text
modify graph
create node
connect node
activate graph node
```

This keeps window placement entirely inside Niri.

---

# 13. Native Overview

Niri's native Overview becomes the Overview for the Niri session.

It should be bound to a convenient key, initially proposed as:

```text
Super + Tab
```

This intentionally mirrors the user's existing muscle memory.

The existing Hyprland behavior remains unchanged:

```text
Hyprland:
Super + Tab → DMS Overview

Niri:
Super + Tab → Niri Overview
```

This gives both sessions a consistent conceptual shortcut without sharing implementation.

Niri's Overview is already designed to zoom out workspaces and windows, navigate the workspace layout, and move windows interactively.

---

# 14. Window Rules

Phase 29 should introduce only the minimum window rules required to demonstrate that named workspaces work correctly.

Rules should be based on observable application identifiers such as:

```text
app-id
title
```

rather than fragile window titles whenever possible.

The initial rule set should remain intentionally small.

Example conceptual mapping:

```text
Browser
    ↓
browser

Code editor / terminal
    ↓
code

Communication application
    ↓
communication
```

However, actual application rules should only be added after verifying their real Niri `app-id` values.

No assumptions should be made from package names or executable names.

---

# 15. Rule Design Principle

Workspace assignment should be deterministic but conservative.

The preferred order is:

```text
specific application
        ↓
specific workspace
```

rather than broad rules such as:

```text
all GTK applications
all Qt applications
all terminals
all browsers
```

Broad rules could unexpectedly capture applications and make debugging harder.

---

# 16. Monitor Behavior

Niri named workspaces can optionally use `open-on-output`.

However, Phase 29 should not immediately hard-code workspace-to-monitor placement unless the physical monitor configuration has first been inspected.

The current machine has an internal Intel display and NVIDIA hardware, so monitor/output behavior must be verified inside the actual Niri session before introducing persistent output-specific workspace rules.

The initial configuration should therefore prioritize:

```text
named workspace semantics
```

over:

```text
hard-coded monitor topology
```

Once the Niri session has been tested, a later phase can introduce explicit monitor/workspace placement if necessary.

---

# 17. Installation Strategy

Niri should be installed using the Fedora-compatible packaging path rather than manually compiling it unless Fedora packaging proves insufficient.

Current Niri documentation explicitly documents Fedora installation and standalone desktop-session integration. The official integration documentation states that a correctly packaged Niri session places the compositor/session files where GDM and other display managers can discover them.

The exact installation command should be verified against the current Fedora 44 repositories/COPR state immediately before execution.

No installation command should be committed to the dotfiles merely because it appears in upstream documentation.

The implementation phase must first determine:

1. whether `niri` is available from the currently enabled Fedora repositories;
2. whether a COPR is required;
3. what package version is available;
4. which companion packages are actually required;
5. whether GDM detects the session automatically.

---

# 18. Session Integration

The expected final state is:

```text
GDM
 ├── Hyprland
 └── Niri
```

Selecting Hyprland must continue to start the existing environment.

Selecting Niri must start:

```text
niri-session
```

with the repository-managed configuration.

Niri's official packaging guidance uses a standalone desktop session and a Wayland session descriptor so that it appears in GDM.

No manual modification under `/usr/share` should be used unless absolutely required by packaging.

---

# 19. Repository Deployment

The repository currently does not use a universal GNU Stow deployment model.

Therefore Phase 29 should not introduce Stow solely for Niri.

The implementation should follow the repository's established configuration-management pattern.

Before creating symlinks or deployment scripts, inspect:

```text
scripts/
```

and existing configuration deployment behavior.

If a simple repository directory can map cleanly to:

```text
~/.config/niri/
```

without introducing unnecessary infrastructure, prefer that approach.

---

# 20. Default Configuration Baseline

The initial Niri configuration should start from the current upstream/default Niri configuration rather than from an old third-party dotfile.

Niri explicitly recommends using its default configuration as a starting point, and the default configuration can evolve between releases.

This is particularly important because the Niri configuration syntax and available features continue to evolve.

The implementation phase should record:

```text
niri version
```

and use that version when validating the configuration.

---

# 21. Interaction With DMS

DMS should not be assumed to work identically under Niri.

Phase 29 therefore treats DMS integration as optional and secondary.

The workspace foundation must work with:

```text
Niri alone
```

before attempting to attach the existing DMS environment.

This provides a clean diagnostic boundary:

```text
Niri problem
vs.
DMS integration problem
```

If DMS is started in Niri during a later phase, its Niri support should be evaluated independently.

Niri documentation currently lists DMS among shells that support Niri, but that does not justify migrating the existing DMS setup during this workspace phase.

---

# 22. Hyprland Compatibility

After Phase 29:

```text
Hyprland
```

must continue to have:

```text
WorkspaceGraph
WorkspaceMetadata
DMS Overview
existing keybindings
existing workspace persistence
```

No Niri configuration should import or execute the Hyprland Lua workspace system.

Likewise, Hyprland configuration should not be modified merely to accommodate Niri.

The two systems remain isolated.

---

# 23. State Isolation

Niri must not write to:

```text
~/.local/state/hyprland/workspace-graph.json
~/.local/state/hyprland/workspace-metadata.json
```

and Hyprland must not depend on Niri workspace state.

The intended separation is:

```text
Hyprland state
    └── ~/.local/state/hyprland/

Niri state
    └── Niri-managed runtime/state locations
```

No compatibility state file should be introduced.

---

# 24. Proposed Repository Changes

Expected new files:

```text
niri/
└── .config/
    └── niri/
        └── config.kdl
```

Potential additional files, only if justified by the final modular structure:

```text
niri/.config/niri/workspaces.kdl
niri/.config/niri/binds.kdl
niri/.config/niri/rules.kdl
```

Documentation:

```text
docs/phases/29-niri-workspace-foundation.md
```

Potential scripts should only be added if the existing repository architecture requires them.

---

# 25. Files Explicitly Not Modified

The following should remain unchanged in Phase 29 unless an implementation issue proves a minimal compatibility change necessary:

```text
hypr/.config/hypr/hyprland.lua

hypr/.config/hypr/modules/workspaces.lua

hypr/.config/hypr/modules/workspace_metadata.lua

hypr/.config/hypr/modules/keybinds.lua

hypr/.config/hypr/modules/dms.lua

dms/overrides/Modules/WorkspaceOverlays/

tests/layout/
```

In particular, the custom `GraphLayout.js` must not be converted into a Niri workspace layout engine.

---

# 26. Implementation Sequence

## Step 1 — Preflight

Verify:

```text
git status
```

Verify current branch and repository cleanliness.

Verify:

```text
command -v niri
niri --version
```

Expected initial state:

```text
niri not installed
```

Record current display/session state.

---

## Step 2 — Inspect Niri packaging

Determine:

* Fedora package availability
* required repositories
* package version
* session files
* systemd user integration
* Xwayland integration
* portal integration

Do not install anything until the dependency boundary is understood.

---

## Step 3 — Install Niri

Install only the packages required for the Niri session.

Do not install a complete third-party desktop configuration.

After installation verify:

```text
command -v niri
niri --version
```

---

## Step 4 — Verify GDM session

Confirm that GDM exposes Niri as a separate session.

Do not modify the existing Hyprland session.

---

## Step 5 — Create repository configuration

Create the Niri configuration directory in the repository.

Begin from the installed/upstream version-compatible default configuration.

Do not immediately replace the entire default configuration with a custom minimal file.

---

## Step 6 — Establish named workspaces

Introduce the initial semantic workspace set:

```text
main
code
browser
communication
media
gaming
```

Validate the syntax before starting a full session.

---

## Step 7 — Add workspace bindings

Add the approved workspace bindings.

Validate:

* focus
* movement
* relative navigation
* Overview
* window movement

---

## Step 8 — Add minimal window rules

Only add rules whose application identifiers have been verified.

Avoid speculative rules.

---

## Step 9 — Start Niri

Log into Niri from GDM.

Do not yet attempt to reproduce the entire Hyprland desktop.

The first test target is:

```text
Niri starts
↓
keyboard works
↓
windows open
↓
workspaces exist
↓
navigation works
↓
Overview works
```

---

# 27. Validation Matrix

## Installation

```text
niri --version
```

Must succeed.

---

## Configuration

```text
niri validate
```

Must return successfully.

Niri officially provides this validation command for configuration parsing.

---

## Session

Verify:

```text
echo "$XDG_SESSION_TYPE"
```

Expected:

```text
wayland
```

Verify the compositor/session corresponds to Niri.

---

## Workspaces

Verify that:

```text
main
code
browser
communication
media
gaming
```

exist.

---

## Persistence

Verify that named workspaces remain available when empty.

This is expected behavior for Niri named workspaces.

---

## Navigation

Test every workspace destination.

Expected:

```text
Super+1 → main
Super+2 → code
Super+3 → browser
Super+4 → communication
Super+5 → media
Super+6 → gaming
```

assuming these bindings are approved during implementation.

---

## Window movement

Open a test window.

Move it between at least:

```text
main ↔ code
code ↔ browser
browser ↔ media
```

Verify that the window follows the workspace correctly.

---

## Overview

Verify:

```text
Super+Tab
```

opens Niri's native Overview.

Verify:

* workspace visibility
* window visibility
* workspace navigation
* window movement
* exit behavior

---

## Hyprland regression

Log back into Hyprland.

Verify:

```text
WorkspaceGraph
workspace navigation
DMS Overview
workspace metadata
```

continue to work exactly as before.

---

# 28. Failure Boundaries

If Niri does not start:

Do not immediately modify Hyprland.

Investigate:

```text
GDM session
niri-session
systemd user services
graphics device selection
Wayland environment
journal logs
```

If Niri starts but workspaces fail:

Investigate only the Niri configuration.

If Niri works but DMS fails:

Treat this as a separate DMS integration issue.

Do not mix the two problems.

---

# 29. Rollback

Phase 29 must be reversible.

Rollback consists of:

1. Select Hyprland from GDM.
2. Verify Hyprland remains functional.
3. Remove or disable the Niri session if required.
4. Remove Niri configuration from the deployed `~/.config/niri/`.
5. Remove only packages introduced specifically for Niri if they are not required elsewhere.
6. Leave all existing Hyprland and DMS files untouched.

Because the Hyprland workspace architecture is not modified, rollback should not require restoring any Hyprland workspace files.

---

# 30. Security and System Integrity

Do not:

* modify `/usr/share` manually unless required by packaging;
* overwrite system configuration files unnecessarily;
* disable SELinux;
* disable security services to make Niri work;
* modify GPU drivers as part of workspace setup;
* replace existing portal configuration globally without justification;
* copy Arch-specific installation commands into Fedora scripts.

All system-level changes must be identified before execution.

---

# 31. Documentation Requirements

During implementation record:

```text
Niri version
Fedora package source
installed packages
session integration method
configuration location
workspace names
binding decisions
window-rule decisions
validation results
known limitations
rollback procedure
```

If an installation detail differs from upstream documentation because Fedora 44 packages it differently, document the Fedora-specific behavior.

---

# 32. Commit Boundary

Phase 29 should not be committed until:

```text
git status
git diff
git diff --check
```

have been reviewed.

The final commit should contain only changes belonging to Phase 29.

Suggested commit:

```text
feat(niri): add workspace foundation
```

If the implementation is split into multiple logical commits, each commit must remain independently understandable.

---

# 33. Acceptance Criteria

Phase 29 is complete when all of the following are true:

* [ ] Niri is installed through a Fedora-compatible method.
* [ ] Niri appears as a selectable GDM session.
* [ ] Hyprland remains selectable.
* [ ] Niri starts successfully.
* [ ] Niri configuration is stored in the dotfiles repository.
* [ ] `niri validate` succeeds.
* [ ] Named workspaces are defined.
* [ ] Workspace navigation works.
* [ ] Window movement between workspaces works.
* [ ] Native Overview works.
* [ ] Minimal window rules work where implemented.
* [ ] No Hyprland WorkspaceGraph files were removed.
* [ ] No DMS workspace overrides were removed.
* [ ] No broad application migration was performed.
* [ ] No theme migration was performed.
* [ ] No NVIDIA optimization was performed.
* [ ] Hyprland regression testing passes.
* [ ] `git diff --check` passes.
* [ ] Final diff contains only Phase 29 changes.
* [ ] Rollback path is documented.

---

# 34. Future Phases

The following should remain candidates for later phases rather than being pulled into Phase 29:

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

### Multi-monitor workspace policy

Potentially:

```text
workspace → output
```

after actual Niri monitor behavior has been observed.

### Niri-specific automation

Only after the basic configuration has remained stable.

---

# 35. Architectural Summary

The final Phase 29 architecture is intentionally simple:

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
                   │       ├── window rules
                   │       └── native Overview
                   │
                   ├── WorkspaceGraph
                   ├── WorkspaceMetadata
                   └── DMS custom Overview
```

The key architectural boundary is:

```text
Hyprland workspace state ≠ Niri workspace state
```

Niri should use Niri's own primitives instead of carrying forward an abstraction designed specifically for Hyprland.

This keeps the migration reversible, avoids duplicate workspace state, and leaves the existing Hyprland environment untouched while Niri is evaluated as an independent session.

---

# 36. Final Decision

Phase 29 adopts **Option B: independent Niri workspace architecture**.

The initial Niri workspace model is:

```text
main
code
browser
communication
media
gaming
```

with semantic navigation and Niri's native Overview.

No custom workspace graph will be introduced for Niri.

No existing Hyprland workspace infrastructure will be removed.

No broad application or desktop-shell migration will occur.

The first implementation milestone is therefore not:

```text
"make Niri look like the current desktop"
```

but:

```text
"prove that Niri can provide a clean, stable, semantic workspace environment
alongside the existing Hyprland environment."
```

Only after that foundation is validated should subsequent phases integrate the rest of the desktop.
