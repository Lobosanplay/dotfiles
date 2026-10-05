# Project Agent Contract

## 1. Project context

This repository contains personal dotfiles for Fedora and Hyprland. The known stack includes:

- Fedora 44 and Hyprland 0.56.2, configured with Lua.
- DMS (DankMaterialShell) / Quickshell for the visual shell.
- A project-owned WorkspaceGraph in Lua, persisted at `~/.local/state/hyprland/workspace-graph.json` and integrated with DMS/Quickshell.
- Intel integrated graphics as the compositor's primary GPU, with an NVIDIA RTX 3050 Laptop GPU available through PRIME Render Offload.
- Kitty as the terminal, Matugen as part of the existing theming system, DMS overrides, and tests for WorkspaceGraph layout.
- Git as the repository's version control system.

The project takes visual inspiration from 43PR/dotfiles; it does not aim to copy that repository's architecture. Adapt useful visual ideas to this project's existing Fedora-based stack.

## 2. Architecture to preserve

Hyprland/Lua is the authority for the WorkspaceGraph, its persistence, and workspace dispatch. DMS/Quickshell presents and interacts with that graph.

```text
Hyprland / Lua
    ├── WorkspaceGraph authority
    ├── graph persistence
    └── workspace dispatch
            │
            ▼
    workspace-graph.json
            │
            ▼
    DMS / Quickshell
    ├── overview
    ├── graph layout
    ├── thumbnails
    └── interaction
```

Do not replace this system with Hyprspace, Hyprexpo, a linear workspace manager, another workspace graph, or a parallel implementation of the same concept. Understand the existing implementation before changing anything related to WorkspaceGraph.

## 3. DMS / Quickshell

DMS/Quickshell is the project's primary visual shell. Do not create a second full desktop shell to replace it. Before implementing a visual feature, check whether DMS already provides it.

Avoid unnecessarily duplicating the bar, launcher, settings, notifications, power menu, lock screen, OSD, wallpaper/dashboard, or overview. For customizing existing DMS functionality, prefer, in order:

1. Existing configuration.
2. An extension or plugin.
3. A controlled override.
4. A new implementation only when the preceding options are insufficient.

Do not directly modify files under `/usr/share` as the normal customization method.

## 4. Compatibility and dependencies

This project targets Fedora. Do not assume Arch Linux, `pacman`, AUR, `yay`, `paru`, Arch-specific paths, or Arch-only package names. Do not run external dotfiles installers such as `43PR/dotfiles` installers, or copy another distribution's install/update scripts without analysis and an explicitly scoped phase.

Do not add dependencies merely because another dotfiles repository uses them. A new dependency needs a clear technical justification and must belong to a defined phase.

## 5. Inspect before modifying

Do not modify files based only on assumptions. Before making changes:

1. Inspect the relevant repository structure.
2. Read the files to be changed and related configuration.
3. Review documentation for relevant earlier phases.
4. Identify dependencies between components and assess the change's impact.
5. Establish a coherent plan before editing.

Do not overwrite existing configuration to simplify it, or remove code before understanding its purpose.

## 6. Required workflow

Follow this cycle for implementation phases:

```text
INSPECT → PLAN → MODIFY → VALIDATE → DOCUMENT → REVIEW DIFF → COMMIT → REVALIDATE
```

- **Inspect:** Understand the current state and relevant dependencies.
- **Plan:** Define the objective, affected files, architecture, risks, implementation, and validation.
- **Modify:** Make only changes needed for the phase.
- **Validate:** Check functionality and regressions.
- **Document:** Record what was actually implemented and the technical decisions in the phase documentation.
- **Review diff:** Check `git status`, `git diff`, `git diff --check`, and relevant tests.
- **Commit:** Create a commit dedicated to the phase or logical unit.
- **Revalidate:** After committing, verify the repository is in the expected state.

## 7. Phase documentation

Keep documentation for each significant project phase in `docs/phases/`, named `<number>-<phase-name>.md`, for example `docs/phases/16-43pr-audit.md` or `docs/phases/17-theme-foundation.md`.

As applicable, record the objective, context, status, scope, design and architecture decisions, changed files, implementation, relevant commands, validations and results, problems and solutions, known limitations, risks, future work, and associated commit. Describe only what was actually implemented; do not present hypothetical functionality as complete.

## 8. Permanent contract vs. phase history

`AGENTS.md` contains permanent project rules. `docs/phases/*.md` records technical history for individual phases. Do not turn this file into a changelog or add temporary phase details here. Permanent architecture decisions may also be documented in `docs/architecture/`; independent technical decisions may be recorded in `docs/decisions/`.

## 9. Git

Check `git status` before and after changes, and review `git diff` and `git diff --check` after editing.

- Never run `git reset --hard`.
- Preserve existing user changes and do not overwrite unrelated work.
- Do not delete existing backups automatically.
- Do not commit changes unrelated to the phase.
- Do not push automatically.
- Use identifiable, coherent commits with clear messages for each phase.

Preserve any pre-existing uncommitted changes.

## 10. Backups and existing files

Treat existing backups as deliberate unless their status is established. Do not delete them automatically. Preserve backups related to WorkspaceGraph or earlier migrations unless an explicitly scoped phase determines they are no longer needed. Backup removal requires an explicit, documented decision.

## 11. Visual design

Visual inspiration from 43PR/dotfiles does not authorize copying its full architecture, installer, update system, linear workspace management, or shell. Adapt visual features to the existing stack; do not introduce Arch-specific tools just to reproduce an appearance.

Priorities are visual coherence, DMS integration, consistent tokens, maintainability, reversibility, Fedora compatibility, and performance.

## 12. Theming system

Avoid multiple sources of truth for colors and visual tokens. When implementing the theme system, prefer semantic tokens that can feed Hyprland, DMS/Quickshell, Kitty, GTK, Hyprlock, and other compatible components where appropriate. Matugen may be part of this system. Extend the existing generator when suitable instead of creating an independent one. Theme implementation details belong to their designated phases, not unrelated tasks.

## 13. Technical validation

A phase is not complete just because it looks right. Scale validation to the change. Where relevant, run existing and new tests, validate syntax and configuration, check that Hyprland loads the configuration and DMS/Quickshell starts, verify affected components, inspect relevant logs, and review the Git diff.

Never claim a validation result that was not obtained. Document validations that could not be run and the limitation.

## 14. Out-of-scope changes

Stop and request an explicitly scoped phase if completing a task requires changing the primary architecture, replacing DMS, changing the workspace manager, installing many dependencies, changing compositor or distribution, modifying drivers or the global graphics system, changing unrelated components, deleting data, or making destructive changes. Do not silently expand a phase's scope.

## 15. Scope discipline

Keep each phase focused on a concrete objective. If an interesting improvement is not needed for the current objective, do not implement it automatically; record it as possible future work and preserve the agreed scope.

## 16. Reversibility

Prefer small, modular, reversible, and auditable changes. Establish a rollback approach before a high-risk change. Avoid changing multiple components at once when they can be changed incrementally.

## 17. Communication

During a phase, communicate what was found, what is planned and changed, what was validated, what could not be validated, and what remains. Do not declare a phase complete while critical validation is outstanding.

## 18. Rules for future phases

For each new phase:

1. Read this `AGENTS.md` and relevant earlier phase documentation.
2. Inspect the repository's actual state.
3. Define the scope.
4. Implement only that scope.
5. Create or update the corresponding document under `docs/phases/`.
6. Validate and review the diff.
7. Create a dedicated commit.
8. Revalidate after committing.

Use the phase explicitly requested by the user and its current scope document. Do not infer a phase from stale roadmap text or implement work from a different phase.

## 19. Current task boundary

Creating this contract is a documentation and repository-governance task. It does not authorize changes to Hyprland, DMS/Quickshell, scripts, tests, README, dependencies, visual configuration, or system packages; creating the theme system; deleting files or backups; running installers; or pushing commits. Phase 17 must remain unimplemented until undertaken as its own phase.
