# Workspace graph y overview

Resumen de cómo funciona el grafo de workspaces y el overview de Hyprland,
las decisiones tomadas y las opciones para los siguientes pasos.

## Arquitectura

```text
Hyprland (Lua)                          DMS / Quickshell (QML)
──────────────                          ──────────────────────
hypr/.../modules/workspaces.lua         dms/overrides/.../HyprlandOverview.qml
  · grafo left/right/up/down              · lee workspace-graph.json (FileView)
  · navigate / activate / connect         · una sola superficie, monitor con foco
  · remove + borrado automático           · teclas: ←↑→↓ selección, ENTER, ESC
  · guarda ~/.local/state/hyprland/     dms/overrides/.../OverviewWidget.qml
    workspace-graph.json  ───────────▶    · layout de grafo + escalado
hypr/.../modules/keybinds.lua             · líneas, miniaturas reales (DMS)
  · SUPER+ALT+flechas → navigate          · números pequeños, cuadros vacíos
hypr/.../modules/dms.lua                scripts/dms-overlay.sh + systemd drop-in
  · SUPER+TAB → overview de DMS           · overlay = paquete DMS + 2 overrides
```

Archivos:

| Archivo | Función |
|---|---|
| `hypr/.config/hypr/modules/workspaces.lua` | Modelo del grafo, navegación, persistencia y borrado automático |
| `hypr/.config/hypr/modules/keybinds.lua` | Atajos propios, incluidos `SUPER + ALT + flechas` |
| `hypr/.config/hypr/modules/dms.lua` | Integración con DMS: colores, reglas de capas y atajos que no chocan |
| `dms/overrides/Modules/WorkspaceOverlays/*.qml` | Copias modificadas del overview de DMS 1.6.2 (cambios marcados con `dotfiles:`) |
| `dms/overrides/**/*.upstream-sha256` | Huella del archivo original de DMS del que parte cada copia |
| `scripts/dms-overlay.sh` | Genera `~/.local/share/dms-overlay/` (enlaces al paquete + copias propias) |
| `systemd/.config/systemd/user/dms.service.d/overlay.conf` | Arranca DMS desde la overlay; si falla, usa el DMS normal |

Estado del grafo: `~/.local/state/hyprland/workspace-graph.json`.

### Atajos

| Atajo | Acción |
|---|---|
| `SUPER + TAB` / `SUPER + O` | Abrir/cerrar el overview |
| `←` `↑` `→` `↓` (en el overview) | Mover la selección |
| `ENTER` / clic (en el overview) | Ir al workspace seleccionado y cerrar |
| `ESC` (en el overview) | Cerrar sin cambiar de workspace |
| `SUPER + ALT + flechas` | Navegar por el grafo; crea un workspace si no hay conexión en esa dirección (teclado 60 %: Fn primero) |
| `SUPER + F` | Maximizar / restaurar la ventana |
| `SUPER + ALT + X` | Salir de Hyprland |

## Cronología

| Commit | Cambio |
|---|---|
| `0984c70` | Grafo de workspaces persistente |
| `db9b00c` V1 | Viewer GTK4 + gtk4-layer-shell (Python): overlay centrado, solo lectura |
| `44f7d34` V2 | Flechas para seleccionar y ENTER para activar |
| `617934e` V3 | Pantalla completa y transparente, activo en el centro, escalado uniforme, multimonitor |
| `a95f8a3` V4 | Minimapas de ventanas desde `hl.get_windows()`; arreglo de `pkill`, que mataba editores |
| `088ea41` | Integración de DMS: config modular restaurada, ciclo de systemd arreglado |
| `5ea3f11` | Unificación: el overview de DMS usa el layout del grafo y conserva sus miniaturas reales |
| `d6dba95` | Salida en `SUPER + ALT + X`, `SUPER + F` para maximizar, viewer GTK eliminado |
| `2dcc2dd` | Borrado automático de workspaces vacíos del grafo, con reconexión en línea recta |
| `23687ec` | Arreglo: el layout ya no salta al abrir (el grafo se carga antes) |
| `788e6f1` | Arreglo: el clic cierra el overview (bug del propio DMS) |

## Decisiones

1. **Overview de DMS en vez del viewer GTK.** Quickshell puede mostrar el
   contenido real de las ventanas; el viewer GTK necesitaba protocolos de
   captura. Tener dos viewers además causaba conflictos de teclado.
2. **Sin plugins de Hyprland (Hyprspace, hyprexpo).** Hyprland del COPR
   `ashbuk/Hyprland-Fedora` trae sus propias copias de aquamarine, hyprutils,
   hyprlang, hyprgraphics y hyprcursor sin cabeceras; un plugin compilado
   contra otras versiones cierra el compositor.
3. **Copias mínimas sin tocar `/usr/share`.** La overlay de enlaces se
   regenera en cada arranque de DMS. Solo hay 2 archivos propios, con la huella
   del original; el script avisa en el journal (*"changed upstream"*) si DMS
   cambia ese original. Si la overlay falla, DMS arranca su versión normal.
4. **Una sola superficie del overview** en el monitor con foco. Con una por
   monitor, el teclado acababa en la superficie equivocada.
5. **Navegación:** primero las conexiones del grafo; si no hay ninguna en esa
   dirección, el workspace más cercano en pantalla dentro de un cono de 45°.
   Las flechas solo seleccionan; ENTER o el clic confirman.
6. **Borrado como en Hyprland:** solo workspaces vacíos que se abandonan.
   `A ─ X ─ B` pasa a `A ─ B` si X los unía en línea recta (opción b).
   `workspace.removed` solo trae el workspace expirado, así que los ids
   borrados se detectan comparando con una foto de los workspaces vivos.
7. **El overview lee `workspace-graph.json`**, porque QML no puede pedir datos
   a la API Lua (`hyprctl dispatch` solo devuelve `ok`). El archivo se lee en
   el `Scope` del overview, que está siempre vivo, para que el grafo ya esté
   cargado al abrir.
8. **Integración selectiva de DMS:** mandan los módulos propios; de DMS solo
   se cargan los colores (`dms/colors.lua`, si existe) y los atajos que no
   chocan. Los archivos de `~/.config/hypr/dms/` los genera DMS y no van al repo.

## Limitaciones conocidas

- Si dos caminos del grafo apuntan a la misma celda, uno se coloca en el hueco
  libre más cercano y su línea sale en diagonal.
- Grafos grandes: las miniaturas se encogen para que todo quepa; no hay
  desplazamiento ni zoom.
- El activo no siempre queda en el centro exacto: se prioriza que el grafo
  quepa grande.
- Para mantener una estructura hay que tener ventanas en ella, porque los
  workspaces vacíos se borran.
- Si DMS cambia los dos archivos originales, hay que revisar las copias a mano.
- Al usuario le falta el grupo `input`, que algunas funciones de DMS necesitan
  (`sudo usermod -aG input $USER`).
- Al salir, Hyprland se estrella en el apagado (bug de aquamarine/EGL) y deja
  un volcado `SIGSEGV`; no afecta al uso normal.

## Siguientes pasos

**A. Editar el grafo desde el overview** (recomendado)
- Mover un workspace, conectar o desconectar con atajos o arrastrando.
- Tecla `x` para borrar a mano (`WorkspaceGraph.remove` ya existe).
- Crear un workspace nuevo desde un cuadro vacío.

**B. Mejorar el layout**
- Evitar líneas en diagonal recolocando los componentes que chocan.
- Zoom o desplazamiento para grafos grandes, y centrado exacto en el activo.

**C. Experiencia visual**
- Animaciones de apertura y de selección (DMS ya trae curvas y duraciones).
- Nombres de workspace con el renombrado de DMS (`CTRL + SHIFT + R` quedó
  fuera porque choca con los navegadores).
- Iconos de las apps.

**D. Robustez**
- Pruebas automáticas del layout en JS y un script que compare las copias con
  DMS tras cada actualización.
- Guardar en el grafo en qué monitor está cada workspace.
