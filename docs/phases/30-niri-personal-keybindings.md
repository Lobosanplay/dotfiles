# Phase 30 — Niri Personal Keybindings

## Status

**Complete**

## Date

2026-10-06

## Objective

Corregir y modularizar los keybindings personales de la sesión Niri para conservar los controles de aplicaciones utilizados previamente en Hyprland/DMS, sustituyendo los defaults de Niri que no corresponden al entorno del usuario.

Esta fase es una corrección posterior a Phase 29 y no modifica la arquitectura de workspaces semánticos introducida allí.

## Scope

### Included

* Mantener `Super + Space` como acceso a DMS Spotlight.
* Asignar `Super + T` a Kitty.
* Asignar `Super + D` a DMS Launcher.
* Mantener `Super + Q` para cerrar la ventana activa.
* Mover estos controles personales a `niri/.config/niri/binds.kdl`.
* Eliminar los bindings personales equivalentes del `config.kdl` base de Niri.
* Sincronizar la configuración versionada con la configuración activa de Niri.
* Validar sintaxis y funcionalidad.
* Registrar el problema de sincronización descubierto durante la implementación.

### Excluded

* Cambios en WorkspaceGraph de Hyprland.
* Cambios en la arquitectura de DMS.
* Cambios en NVIDIA/PRIME/drivers.
* Cambios en portales XDG.
* Cambios en workspaces semánticos.
* Cambios en monitores u output placement.
* Instalación o eliminación de aplicaciones.
* Sustitución de DMS por Fuzzel u otro launcher.
* Sustitución de Kitty por Alacritty.

## Context

Phase 29 introdujo Niri como una segunda sesión Wayland independiente de Hyprland y estableció workspaces semánticos nativos mediante:

* `main`
* `code`
* `browser`
* `communication`
* `media`
* `gaming`

Los bindings de workspaces ya estaban correctamente definidos en:

```text
niri/.config/niri/binds.kdl
```

Sin embargo, los controles personales de aplicaciones todavía no estaban modularizados y Niri conservaba sus defaults para:

```text
Mod+T → alacritty
Mod+D → fuzzel
Mod+Q → close-window
```

El comportamiento deseado era conservar la experiencia utilizada anteriormente en Hyprland/DMS:

```text
Super+Space → DMS Spotlight
Super+T     → Kitty
Super+D     → DMS Launcher
Super+Q     → cerrar ventana
```

## Existing Hyprland/DMS Behavior Audited

La configuración existente fue inspeccionada antes de modificar Niri.

### Spotlight

El comportamiento previo de `Super + Space` estaba definido por DMS:

```text
dms ipc call spotlight toggle
```

### Terminal

El comportamiento previo de `Super + T` utilizaba:

```text
kitty
```

### Launcher

El comportamiento previo de `Super + D` utilizaba:

```text
dms ipc call launcher toggle
```

### Close Window

El comportamiento previo de `Super + Q` cerraba la ventana activa mediante la integración de Hyprland.

La auditoría confirmó que estos comportamientos debían preservarse en Niri.

## Implementation

### Personal bindings

Los controles personales fueron añadidos a:

```text
niri/.config/niri/binds.kdl
```

Configuración final:

```kdl
// Personal application controls.
Mod+Space { spawn "dms" "ipc" "call" "spotlight" "toggle"; }
Mod+T { spawn "kitty"; }
Mod+D { spawn "dms" "ipc" "call" "launcher" "toggle"; }
Mod+Q repeat=false { close-window; }
```

Esto mantiene separados:

* workspaces semánticos;
* navegación de workspaces;
* controles personales de aplicaciones.

### Base Niri configuration

Los bindings personales equivalentes fueron eliminados de:

```text
niri/.config/niri/config.kdl
```

Se eliminaron los defaults:

```kdl
Mod+T hotkey-overlay-title="Open a Terminal: alacritty" { spawn "alacritty"; }
Mod+D hotkey-overlay-title="Run an Application: fuzzel" { spawn "fuzzel"; }
Mod+Q repeat=false { close-window; }
```

El Overview nativo de Niri permaneció sin cambios:

```kdl
Mod+O repeat=false { toggle-overview; }
```

## Synchronization Issue Discovered

Durante la validación funcional se detectó que la configuración versionada y la configuración activa de Niri eran dos archivos regulares independientes.

La configuración activa:

```text
~/.config/niri/config.kdl
~/.config/niri/binds.kdl
```

no eran symlinks hacia:

```text
~/Documents/projects/dotfiles/niri/.config/niri/
```

Por lo tanto, modificar el repositorio no modificaba automáticamente la configuración utilizada por la sesión Niri.

Inicialmente se validó correctamente:

```text
niri/.config/niri/config.kdl
```

pero Niri continuaba ejecutando la copia anterior ubicada en:

```text
~/.config/niri/config.kdl
```

Esto explicó por qué:

```bash
niri msg action load-config-file
```

no produjo el comportamiento esperado: Niri estaba recargando una configuración activa que todavía contenía los defaults anteriores.

## Synchronization Procedure

Antes de sobrescribir la configuración activa se crearon backups:

```text
~/.config/niri/config.kdl.before-personal-keybindings
~/.config/niri/binds.kdl.before-personal-keybindings
```

Posteriormente se sincronizaron los archivos versionados:

```text
niri/.config/niri/config.kdl
    ↓
~/.config/niri/config.kdl

niri/.config/niri/binds.kdl
    ↓
~/.config/niri/binds.kdl
```

La configuración activa fue recargada sin cerrar la sesión.

## Final Behavior

La validación funcional confirmó:

| Binding         | Resultado                 |
| --------------- | ------------------------- |
| `Super + Space` | DMS Spotlight             |
| `Super + T`     | Kitty                     |
| `Super + D`     | DMS Launcher              |
| `Super + Q`     | Cierra la ventana activa  |
| `Super + 1`     | Workspace `main`          |
| `Super + 2`     | Workspace `code`          |
| `Super + 3`     | Workspace `browser`       |
| `Super + 4`     | Workspace `communication` |
| `Super + 5`     | Workspace `media`         |
| `Super + 6`     | Workspace `gaming`        |
| `Super + Tab`   | Workspace anterior        |
| `Super + O`     | Overview nativo de Niri   |

## Validation

### Git status

Expected changed files:

M  niri/.config/niri/binds.kdl
M  niri/.config/niri/config.kdl
?? docs/phases/30-niri-personal-keybindings.md

No unrelated files were modified.

### Diff review

The final diff contains only:

1. addition of personal application bindings to `binds.kdl`;
2. removal of the corresponding Niri default application bindings from `config.kdl`.

No workspace architecture was altered.

### Git diff check

```bash
git diff --check
```

Result:

```text
PASS
```

No whitespace errors were reported.

### Niri configuration validation

```bash
niri validate -c niri/.config/niri/config.kdl
```

Result:

```text
INFO niri: config is valid
```

### Functional validation

The active configuration was synchronized with the repository and reloaded.

Manual testing confirmed that all requested personal keybindings work correctly.

## Acceptance Criteria

| Criterion                                           | Status |
| --------------------------------------------------- | ------ |
| `Super + Space` opens DMS Spotlight                 | PASS   |
| `Super + T` opens Kitty                             | PASS   |
| `Super + D` opens DMS Launcher                      | PASS   |
| `Super + Q` closes active window                    | PASS   |
| Niri no longer uses Alacritty for `Super + T`       | PASS   |
| Niri no longer uses Fuzzel for `Super + D`          | PASS   |
| Personal bindings are modularized in `binds.kdl`    | PASS   |
| Niri Overview remains available through `Super + O` | PASS   |
| Semantic workspaces remain unchanged                | PASS   |
| Hyprland configuration remains untouched            | PASS   |
| DMS configuration remains untouched                 | PASS   |
| Niri configuration validates successfully           | PASS   |
| `git diff --check` passes                           | PASS   |
| Active configuration synchronized with repository   | PASS   |
| Functional testing completed                        | PASS   |

## Files Changed

```text
niri/.config/niri/binds.kdl
niri/.config/niri/config.kdl
docs/phases/30-niri-personal-keybindings.md
```

## Backups

Created before synchronization:

```text
~/.config/niri/config.kdl.before-personal-keybindings
~/.config/niri/binds.kdl.before-personal-keybindings
```

These backups preserve the previous active Niri configuration and can be used for rollback if required.

## Rollback

To restore the previous active configuration:

```bash
cp -a ~/.config/niri/config.kdl.before-personal-keybindings \
    ~/.config/niri/config.kdl

cp -a ~/.config/niri/binds.kdl.before-personal-keybindings \
    ~/.config/niri/binds.kdl
```

Then reload Niri:

```bash
niri msg action load-config-file
```

The repository files should not be reverted solely to roll back the active configuration unless the repository itself is intentionally being reverted.

## Architectural Result

Niri now follows the intended modular structure:

```text
niri/
└── .config/
    └── niri/
        ├── config.kdl
        ├── workspaces.kdl
        └── binds.kdl
```

Responsibilities:

```text
config.kdl
    Base Niri configuration
    Input
    Outputs
    Layout
    Rules
    Animations
    Overview
    Session-level defaults

workspaces.kdl
    Semantic workspace definitions

binds.kdl
    Workspace navigation
    Workspace movement
    Personal application controls
```

This preserves the separation established in Phase 29 while keeping personal keybindings out of the large upstream-derived `config.kdl`.

## Known Limitation

The repository currently stores Niri configuration separately from the active files under `~/.config/niri/`.

They are regular files rather than symlinks.

Therefore future modifications to the repository's Niri configuration must explicitly synchronize the active configuration before testing the running Niri session.

This is an operational consideration for future Niri phases.

## Future Work

Potential future phases may address:

* application-specific Niri window rules;
* output-specific workspace placement;
* additional Niri/DMS integration;
* further modularization of the base Niri configuration;
* optional automation for deploying Niri dotfiles.

These are intentionally outside the scope of Phase 30.

## Final Status

**Phase 30 complete.**

The Niri personal keybindings now reproduce the intended user workflow:

```text
Super + Space → DMS Spotlight
Super + T     → Kitty
Super + D     → DMS Launcher
Super + Q     → Close Window
```

The configuration is modular, validated, synchronized with the active session, and functionally verified.
