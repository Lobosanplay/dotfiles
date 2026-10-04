# Workspace graph y overview

Resumen de cómo funciona el grafo de workspaces y el overview de Hyprland,
las decisiones tomadas y las opciones para los siguientes pasos.

## Arquitectura

```text
Hyprland (Lua, autoridad del estado)    DMS / Quickshell (QML, presentación)
────────────────────────────────────    ────────────────────────────────────
modules/workspaces.lua                  dms/overrides/.../HyprlandOverview.qml
  · WorkspaceGraph: grafo, navegación,    · FileView del grafo y de los metadatos
    edición, borrado automático           · una superficie en el monitor con foco
  · workspace-graph.json  ─────────────▶  · teclado, offsets de arrastre (memoria)
modules/workspace_metadata.lua          dms/overrides/.../OverviewWidget.qml
  · WorkspaceMetadata: nombres, iconos    · miniaturas reales de DMS, líneas
  · workspace-metadata.json  ──────────▶  · selección, arrastre, cámara (zoom/pan)
modules/dms.lua                         dms/overrides/.../GraphLayout.js
  · WorkspaceOverview: órdenes del        · layout puro (probado en tests/layout)
    overview ◀──── Lua dispatch ────────
  · SUPER+TAB → overview                scripts/dms-overlay.sh + drop-in systemd
modules/keybinds.lua                      · overlay = paquete DMS + 3 overrides
  · SUPER+ALT+flechas → navigate          · fallback al DMS normal si DMS cambia
```

Archivos:

| Archivo | Función |
|---|---|
| `hypr/.config/hypr/modules/workspaces.lua` | Modelo del grafo, navegación, persistencia y borrado automático |
| `hypr/.config/hypr/modules/keybinds.lua` | Atajos propios, incluidos `SUPER + ALT + flechas` |
| `hypr/.config/hypr/modules/dms.lua` | Integración con DMS: colores, reglas de capas y atajos que no chocan |
| `hypr/.config/hypr/modules/workspace_metadata.lua` | Nombres e iconos por workspace (`WorkspaceMetadata`) |
| `dms/overrides/Modules/WorkspaceOverlays/*.qml` | Copias modificadas del overview de DMS (cambios marcados con `dotfiles:`) |
| `dms/overrides/Modules/WorkspaceOverlays/GraphLayout.js` | Layout del grafo y escala, sin dependencias de QML |
| `dms/overrides/**/*.upstream` | Copia exacta del archivo de DMS del que parte cada override |
| `dms/overrides/UPSTREAM_VERSION` | Versión de DMS contra la que se revisaron los overrides |
| `scripts/dms-overlay.sh` | Genera `~/.local/share/dms-overlay/` (enlaces al paquete + copias propias); `--check`, `--update-base` |
| `systemd/.config/systemd/user/dms.service.d/overlay.conf` | Arranca DMS desde la overlay; si no se construye, usa el DMS normal |
| `tests/layout/*.test.js` | Tests del layout: `node --test 'tests/layout/*.test.js'` |

Estado: `~/.local/state/hyprland/workspace-graph.json` (grafo) y
`~/.local/state/hyprland/workspace-metadata.json` (nombres e iconos).

### API de `WorkspaceGraph` (Lua)

Las funciones de edición devuelven `ok, error` y no modifican nada si la
operación no es válida. Toda modificación válida se guarda (de forma atómica).

| Función | Descripción |
|---|---|
| `navigate(direction)` | Activa el vecino; si no hay, crea uno conectado y lo activa |
| `activate(id)` | Activa el workspace en Hyprland |
| `connect(a, direction, b)` | Conecta en ambos sentidos; rechaza huecos ocupados, `a == b` y pares ya conectados |
| `disconnect(a, direction)` | Quita la conexión en ambos extremos; devuelve el antiguo vecino |
| `create()` | Crea un nodo virtual con el menor id libre y lo devuelve (sin activarlo) |
| `create_neighbor(a, direction)` | Crea un nodo virtual conectado a `a` en esa dirección |
| `remove(id)` | Borra un nodo virtual (no el último); reconecta en línea recta |
| `get_neighbors(id)` | Copia de las conexiones de un nodo |
| `get_workspaces()` | La tabla interna (solo lectura) |
| `get_active_workspace()` | Workspace activo de Hyprland |
| `validate()` | `ok, problemas`: comprueba los invariantes |
| `save()` | Guarda el grafo |

Invariantes: ids enteros positivos; conexiones bidireccionales; sin enlaces a
sí mismo ni dobles entre el mismo par; toda conexión apunta a un nodo. Al
cargar se reparan los archivos que no los cumplan.

**Nodos virtuales:** un nodo puede existir sin workspace en Hyprland (creado
con `create()` o persistido de otra sesión). Es intencionado. Un nodo se borra
automáticamente cuando Hyprland destruye su workspace al quedar vacío; a mano
(`X`) solo se pueden borrar nodos virtuales, así el grafo nunca pierde un
workspace que Hyprland tiene abierto.

El overview no edita el grafo: envía órdenes Lua a `WorkspaceOverview`
(`hypr/.config/hypr/modules/dms.lua`), que llama a `WorkspaceGraph` y muestra
una notificación de Hyprland si la operación se rechaza. Los cambios llegan al
overview a través del JSON, que vigila con `FileView`.

### Atajos

| Atajo | Acción |
|---|---|
| `SUPER + TAB` / `SUPER + O` | Abrir/cerrar el overview |
| `←` `↑` `→` `↓` (en el overview) | Mover la selección |
| `ENTER` / clic (en el overview) | Ir al workspace seleccionado y cerrar |
| `ESC` (en el overview) | Cerrar sin cambiar de workspace |
| `SUPER + SHIFT + flecha` (en el overview) | Conectar el seleccionado con el workspace más cercano en esa dirección; si no hay ninguno, crea uno nuevo conectado |
| `SUPER + CTRL + flecha` (en el overview) | Quitar la conexión del seleccionado en esa dirección |
| `N` (en el overview) | Crear un workspace (virtual) y seleccionarlo |
| `X` (en el overview) | Borrar el workspace seleccionado (solo si es virtual) |
| `R` / `I` (en el overview) | Cambiar el nombre / el icono del seleccionado (`ENTER` guarda, `ESC` cancela, vacío borra) |
| Arrastrar un workspace (en el overview) | Moverlo en pantalla (solo visual, ver abajo) |
| Rueda / `+` `-` (en el overview) | Zoom (la rueda, centrada en el cursor) |
| Botón central arrastrando (en el overview) | Desplazar la vista |
| `0` (en el overview) | Volver a la vista ajustada |
| `SUPER + ALT + flechas` | Navegar por el grafo; crea un workspace si no hay conexión en esa dirección (teclado 60 %: Fn primero) |
| `SUPER + F` | Maximizar / restaurar la ventana |
| `SUPER + ALT + X` | Salir de Hyprland |

## Overview: interacción y presentación

### Drag & drop

Arrastrar un workspace **solo cambia su posición en pantalla**: el grafo y su
JSON no cambian. Los desplazamientos (en celdas) viven en memoria en el
`Scope` de `HyprlandOverview.qml`, así que se conservan al cerrar y reabrir el
overview y se pierden al reiniciar DMS. Al pulsar se selecciona; soltar tras
moverse menos que `Qt.styleHints.startDragDistance` es un clic (activa). Al
soltar, el workspace encaja en la celda más cercana; si está ocupada, vuelve
a su sitio. Las flechas navegan por las posiciones que se ven. Arrastrar una
miniatura de ventana sigue moviendo la ventana a otro workspace (DMS).

### Zoom y pan

Una cámara (zoom, x, y) aplicada como transformación `Scale` + `Translate` a
las capas del overview: el layout no se recalcula y miniaturas, líneas y
etiquetas se escalan juntas. Zoom entre 0,5× y 4×; siempre queda parte del
grafo dentro del panel y la cámara se desplaza para mostrar la selección.
Cada apertura empieza con la vista ajustada. La rueda y el pan usan
`MouseArea`: los *pointer handlers* (`WheelHandler`, `DragHandler`) no reciben
eventos en esta superficie.

### Nombres e iconos

`WorkspaceMetadata` (Lua) guarda un nombre y un icono opcionales por nodo del
grafo, en un archivo aparte para no tocar la validación ni el formato del
grafo. Nombres: hasta 32 bytes, sin comillas, barras invertidas ni
caracteres de control. Iconos: nombres de Material Symbols (`[a-z0-9_]`), la
fuente que trae DMS. Al borrarse un nodo (`WorkspaceGraph.on_removed`) se
borra su metadato, así un id reutilizado no hereda un nombre. Se muestran en
pequeño junto al número, fuera de la miniatura.

| Función | Descripción |
|---|---|
| `WorkspaceMetadata.get(id)` | Copia de `{name, icon}` o `nil` |
| `WorkspaceMetadata.set_name(id, name)` | Vacío o `nil` borra; devuelve `ok, error` |
| `WorkspaceMetadata.set_icon(id, icon)` | Ídem para el icono |
| `WorkspaceMetadata.clear(id)` | Borra los dos |

### Animaciones

Cortas, con `Theme.shortDuration` y `Theme.standardEasing` de DMS (siguen la
velocidad de animación configurada en DMS): el borde de la selección, los
movimientos de cámara con teclado (la rueda y el pan son inmediatos) y la
barra de edición. La apertura y el cierre los anima DMS. No se animan las
miniaturas ni los cambios de layout: las ventanas se colocan con valores
calculados y se separarían de sus celdas.

### Layout

BFS desde el workspace activo sobre una cuadrícula: cada vecino va a la
celda de su dirección. Si está ocupada, `chooseCell` puntúa candidatas (más
lejos en la misma línea, desplazadas a un lado y el anillo alrededor) por el
coste de todas las líneas hacia vecinos ya colocados: lado incorrecto (500),
cruces (100), línea sobre otro workspace (60), diagonal (25) y longitud (1).
Los componentes desconectados van al lado que deja la escala mayor; luego
`fitScale` ajusta todo a la pantalla y el activo se centra si cabe.
Determinista: sin aleatoriedad y con ids y direcciones en orden.

Se descartaron *force-directed* (pierde la semántica de las direcciones y no
es determinista), routing ortogonal (no evita los choques de nodos) y
Sugiyama (pensado para jerarquías).

### Tests

`node --test 'tests/layout/*.test.js'` (sin sesión gráfica; carga el
`GraphLayout.js` real con `vm`):

- casos fijos (uno, dos, vertical, cruz, dos componentes, cadena de 50,
  ciclo, regresión de colisión), con cada workspace como activo y viewports
  1920×1080, 2560×1440, 3840×2160 y 1600×900: posiciones finitas, únicas y
  acotadas; activo en (0, 0); determinismo (también con otro orden del
  JSON); vecinos cerca y en su lado; componentes sin solaparse; el grafo
  cabe en pantalla con `fitScale`;
- calidad en 300 grafos generados con semilla fija: límites de relaciones en
  el lado incorrecto, cruces, líneas sobre workspaces y solapes.

## Mantenimiento frente a actualizaciones de DMS

Cada override de un archivo de DMS lleva junto a él `<archivo>.upstream`,
copia exacta del original del que parte, y `dms/overrides/UPSTREAM_VERSION`
indica la versión de DMS revisada. En cada arranque de DMS,
`dms-overlay.sh` compara esas copias con el DMS instalado:

- **sin cambios:** construye la overlay y DMS la usa;
- **algún original cambió:** no construye la overlay (los overrides dependen
  entre sí), avisa en el journal y con una notificación de Hyprland qué
  archivo cambió, y sale con 3; el servicio arranca el DMS normal. Las copias
  de `dms/overrides` nunca se modifican y no hay reintentos.

Procedimiento tras actualizar DMS:

1. `scripts/dms-overlay.sh --check`: lista los archivos que cambiaron y
   muestra el diff de DMS (base → versión instalada).
2. Llevar esos cambios a la copia propia (los cambios propios están marcados
   con `dotfiles:`), por ejemplo aplicando el diff mostrado.
3. `scripts/dms-overlay.sh --update-base Modules/WorkspaceOverlays/<archivo>`
   por cada archivo revisado.
4. `systemctl --user restart dms.service` y comprobar el overview.
5. `node --test 'tests/layout/*.test.js'` si se tocó el layout.

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
| `7764028` | API de edición de `WorkspaceGraph`, validación y guardado atómico |
| `d84e9e4` | Edición del grafo desde el overview |
| `4d2c5ad` | Arrastrar workspaces |
| `7c4005a` | Zoom y pan |
| `d802637` / `b93a56a` | Nombres e iconos |
| `6d3733b` | Animaciones |
| `7c4948a` / `7d0509b` | Layout en módulo puro y resolución de colisiones |
| `2d33135` / `e1791a9` | `fitScale` en el módulo y tests del layout |

## Decisiones

1. **Overview de DMS en vez del viewer GTK.** Quickshell puede mostrar el
   contenido real de las ventanas; el viewer GTK necesitaba protocolos de
   captura. Tener dos viewers además causaba conflictos de teclado.
2. **Sin plugins de Hyprland (Hyprspace, hyprexpo).** Hyprland del COPR
   `ashbuk/Hyprland-Fedora` trae sus propias copias de aquamarine, hyprutils,
   hyprlang, hyprgraphics y hyprcursor sin cabeceras; un plugin compilado
   contra otras versiones cierra el compositor.
3. **Copias mínimas sin tocar `/usr/share`.** La overlay de enlaces se
   regenera en cada arranque de DMS con 3 archivos propios (2 copias de DMS y
   `GraphLayout.js`). Si DMS cambia uno de los originales, se usa el DMS
   normal hasta revisar (ver Mantenimiento).
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

- Si dos caminos del grafo apuntan a la misma celda, uno queda en diagonal
  (en el lado correcto de su conexión); en ciclos puede quedar alguna línea
  sobre otro workspace.
- Los desplazamientos de arrastre no se guardan entre reinicios de DMS.
- Para arrastrar un workspace hay que agarrarlo por una zona sin ventana; el
  clic central sobre una miniatura cierra la ventana en lugar de desplazar.
- Con zoom alto las miniaturas se ven borrosas (se escala su textura).
- Tras actualizar DMS, el overview del grafo queda desactivado hasta revisar
  los overrides (ver Mantenimiento).
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

- Guardar los desplazamientos de arrastre (requiere decidir si son estado
  visual persistente aparte del grafo).
- Arrastrar workspaces con ventanas desde cualquier punto (p. ej. con un
  modificador).
- Guardar en el grafo en qué monitor está cada workspace.
