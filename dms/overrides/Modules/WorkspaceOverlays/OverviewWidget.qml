import QtQuick
import Quickshell
import Quickshell.Hyprland
import qs.Common
import qs.Services
import qs.Widgets
import "GraphLayout.js" as GraphLayout

Item {
    id: root
    readonly property var log: Log.scoped("OverviewWidget")
    required property var panelWindow
    required property bool overviewOpen

    // dotfiles: asks HyprlandOverview.qml to close the overview. Assigning
    // overviewOpen here only changed this widget's copy, so clicks left the
    // overview open.
    signal closeRequested
    readonly property HyprlandMonitor monitor: Hyprland.monitorFor(panelWindow.screen)
    readonly property real dpr: CompositorService.getScreenScale(panelWindow.screen)
    readonly property int workspacesShown: SettingsData.overviewRows * SettingsData.overviewColumns

    readonly property var allWorkspaces: Hyprland.workspaces?.values || []
    readonly property var allWorkspaceIds: {
        const workspaces = allWorkspaces;
        if (!workspaces || workspaces.length === 0)
            return [];
        try {
            const ids = workspaces.map(ws => ws?.id).filter(id => id !== null && id !== undefined);
            return ids.sort((a, b) => a - b);
        } catch (e) {
            return [];
        }
    }

    readonly property var thisMonitorWorkspaceIds: {
        const workspaces = allWorkspaces;
        const mon = monitor;
        if (!workspaces || workspaces.length === 0 || !mon)
            return [];
        try {
            const filtered = workspaces.filter(ws => ws?.monitor?.name === mon.name);
            return filtered.map(ws => ws?.id).filter(id => id !== null && id !== undefined).sort((a, b) => a - b);
        } catch (e) {
            return [];
        }
    }

    // dotfiles: the workspaces of the graph view (see graphNodes).
    readonly property var displayedWorkspaceIds: Object.keys(graphNodes).map(Number).sort((a, b) => a - b)

    readonly property int minWorkspaceId: displayedWorkspaceIds.length > 0 ? displayedWorkspaceIds[0] : 1
    readonly property int maxWorkspaceId: displayedWorkspaceIds.length > 0 ? displayedWorkspaceIds[displayedWorkspaceIds.length - 1] : workspacesShown
    readonly property int displayWorkspaceCount: displayedWorkspaceIds.length

    readonly property int effectiveColumns: SettingsData.overviewColumns

    // dotfiles: keyboard selection, moved by HyprlandOverview.qml and
    // confirmed with Enter. -1 means nothing selected.
    property int selectedWorkspace: -1

    // dotfiles: workspace graph, provided already loaded by HyprlandOverview.qml.
    property var workspaceGraph: ({})

    function resetSelection() {
        const active = monitor?.activeWorkspace?.id;
        selectedWorkspace = displayedWorkspaceIds.includes(active) ? active : (displayedWorkspaceIds[0] ?? -1);
    }

    // dotfiles: graph edits and activation are Lua dispatches to
    // WorkspaceOverview (hypr/modules/dms.lua); Hyprland owns the graph and
    // the overview only sees the result through workspace-graph.json.
    function graphCommand(lua) {
        Hyprland.dispatch(`function() ${lua} end`);
    }

    function activateWorkspace(id) {
        if (id > 0)
            graphCommand(`WorkspaceOverview.activate(${id})`);
    }

    // dotfiles: keep the selection on a workspace that still exists, and
    // select a workspace created from the overview once it shows up.
    property bool selectNextNewWorkspace: false
    property var previousWorkspaceIds: []

    function expectNewWorkspace() {
        selectNextNewWorkspace = true;
        newWorkspaceTimer.restart();
    }

    Timer {
        id: newWorkspaceTimer
        interval: 2000
        onTriggered: root.selectNextNewWorkspace = false
    }

    onDisplayedWorkspaceIdsChanged: {
        const ids = displayedWorkspaceIds;

        if (selectNextNewWorkspace) {
            const added = ids.filter(id => !previousWorkspaceIds.includes(id));
            if (added.length > 0) {
                selectedWorkspace = added[0];
                selectNextNewWorkspace = false;
            }
        }

        if (!ids.includes(selectedWorkspace))
            resetSelection();

        // A removed workspace's offset must not move a later one with its id.
        const stale = Object.keys(workspaceOffsets).filter(key => !ids.includes(Number(key)));
        if (stale.length > 0) {
            const offsets = Object.assign({}, workspaceOffsets);
            for (const key of stale)
                delete offsets[key];
            workspaceOffsetsEdited(offsets);
        }

        previousWorkspaceIds = ids;
    }

    // -- dotfiles: graph layout -----------------------------------------
    // The layout itself lives in GraphLayout.js (pure, tested in
    // tests/layout): the active workspace sits at (0, 0), its component
    // expands around it by BFS over left/right/up/down, and disconnected
    // components go to the side that keeps the largest scale.

    readonly property var graphDirections: GraphLayout.DIRECTIONS
    readonly property real graphGapRatio: 0.3 // gap between cells, relative to a cell
    readonly property real componentGap: 0.5 // extra grid cells between components
    readonly property real maxGraphScale: Math.max(SettingsData.overviewScale, 0.3)

    // Hyprland's regular workspaces plus every node of the graph.
    readonly property var graphNodes: {
        const nodes = {};
        const add = id => {
            if (id > 0 && nodes[id] === undefined)
                nodes[id] = {};
        };

        for (const id of allWorkspaceIds)
            add(id);

        for (const key in workspaceGraph) {
            const id = parseInt(key);
            const links = workspaceGraph[key] || {};
            add(id);

            for (const direction in graphDirections) {
                const target = links[direction];
                if (id > 0 && typeof target === "number" && target > 0) {
                    add(target);
                    nodes[id][direction] = target;
                }
            }
        }

        return nodes;
    }

    // Largest monitor frame among the shown workspaces, in logical pixels.
    readonly property var maxCellLogical: {
        let width = 1;
        let height = 1;
        for (const id of displayedWorkspaceIds) {
            const logical = monitorLogicalSize(monitorIpcForWorkspace(id));
            width = Math.max(width, logical.width);
            height = Math.max(height, logical.height);
        }
        return {
            "width": width,
            "height": height
        };
    }

    // Room for the graph on this screen (the overview sits 100px from the top).
    readonly property real availableWidth: Math.max((panelWindow.width || monitorPhysicalWidth) - 2 * Theme.spacingL - 96, 1)
    readonly property real availableHeight: Math.max((panelWindow.height || monitorPhysicalHeight) - 100 - 2 * Theme.spacingL - 72, 1)

    readonly property var graphPositions: GraphLayout.layoutGraph(graphNodes, monitor?.activeWorkspace?.id ?? -1, availableWidth / availableHeight, maxCellLogical.height / maxCellLogical.width, graphGapRatio, componentGap)

    // -- dotfiles: drag & drop --------------------------------------------
    // Dragging a workspace only moves it on screen: per-workspace offsets in
    // grid cells, kept in memory by HyprlandOverview.qml for the session.
    // The graph (connections) is never changed by a drag.
    property var workspaceOffsets: ({})
    signal workspaceOffsetsEdited(var offsets)

    // In-progress drag: {"id": workspace, "dx": px, "dy": px}, or null.
    property var dragPreview: null

    // Graph layout plus the user's offsets: what is drawn and what the
    // arrow keys navigate.
    readonly property var effectivePositions: {
        const result = {};
        for (const key in graphPositions) {
            const offset = workspaceOffsets[key] || [0, 0];
            result[key] = [graphPositions[key][0] + offset[0], graphPositions[key][1] + offset[1]];
        }
        return result;
    }

    // -- dotfiles: names and icons -----------------------------------------
    // Shown next to the small workspace number; edited with R (name) and
    // I (icon, a Material Symbols name) through WorkspaceOverview.
    property var workspaceMetadata: ({})
    property int editingWorkspace: -1
    property string editingField: ""
    signal editorClosed

    function startEditing(id, field) {
        if (id <= 0)
            return;
        editingWorkspace = id;
        editingField = field;
        editorInput.text = workspaceMetadata[id]?.[field] ?? "";
        editorInput.selectAll();
        editorInput.forceActiveFocus();
    }

    function finishEditing(save) {
        if (save && editingWorkspace > 0) {
            const value = editorInput.text.replace(/[\u0000-\u001f\u007f]/g, "").trim();
            const command = editingField === "name" ? "rename" : "set_icon";
            graphCommand(`WorkspaceOverview.${command}(${editingWorkspace}, ${JSON.stringify(value)})`);
        }
        editingWorkspace = -1;
        editorClosed();
    }

    // -- dotfiles: zoom and pan --------------------------------------------
    // A camera over the graph, applied as a transform to its layers, so the
    // layout is not recomputed and thumbnails scale with it. Every opening
    // starts with the fitted view (zoom 1, no pan).
    property real cameraZoom: 1
    property real cameraX: 0
    property real cameraY: 0
    readonly property real minCameraZoom: 0.5
    readonly property real maxCameraZoom: 4

    // dotfiles: keyboard camera moves are animated; the wheel and the
    // middle-button pan follow the pointer immediately.
    property bool cameraAnimated: false

    Behavior on cameraZoom {
        enabled: root.cameraAnimated
        NumberAnimation {
            duration: Theme.shortDuration
            easing.type: Theme.standardEasing
        }
    }

    Behavior on cameraX {
        enabled: root.cameraAnimated
        NumberAnimation {
            duration: Theme.shortDuration
            easing.type: Theme.standardEasing
        }
    }

    Behavior on cameraY {
        enabled: root.cameraAnimated
        NumberAnimation {
            duration: Theme.shortDuration
            easing.type: Theme.standardEasing
        }
    }

    component CameraScale: Scale {
        xScale: root.cameraZoom
        yScale: root.cameraZoom
    }

    component CameraTranslate: Translate {
        x: root.cameraX
        y: root.cameraY
    }

    function clamp(value, low, high) {
        return Math.max(low, Math.min(high, value));
    }

    // Sets the camera, keeping part of the graph inside the panel.
    function setCamera(zoom, x, y) {
        zoom = clamp(zoom, minCameraZoom, maxCameraZoom);

        const viewW = overviewBackground.width;
        const viewH = overviewBackground.height;
        const sceneW = workspaceGrid.width * zoom;
        const sceneH = workspaceGrid.height * zoom;
        const keepW = Math.min(sceneW, viewW) * 0.25;
        const keepH = Math.min(sceneH, viewH) * 0.25;

        cameraZoom = zoom;
        cameraX = clamp(x, keepW - sceneW - workspaceGrid.x, viewW - keepW - workspaceGrid.x);
        cameraY = clamp(y, keepH - sceneH - workspaceGrid.y, viewH - keepH - workspaceGrid.y);
    }

    // Zooms by `factor` keeping the point (px, py) of the panel in place.
    function zoomAt(px, py, factor) {
        const x = px - workspaceGrid.x;
        const y = py - workspaceGrid.y;
        const sceneX = (x - cameraX) / cameraZoom;
        const sceneY = (y - cameraY) / cameraZoom;
        const zoom = clamp(cameraZoom * factor, minCameraZoom, maxCameraZoom);
        setCamera(zoom, x - sceneX * zoom, y - sceneY * zoom);
    }

    // Wheel zoom for any MouseArea of the overview (`item` is the MouseArea
    // that received the event). Pointer handlers such as WheelHandler do
    // not receive events in this surface, so MouseAreas handle the wheel.
    function wheelZoom(wheel, item) {
        const steps = wheel.angleDelta.y / 120;
        if (steps === 0)
            return;
        cameraAnimated = false;
        const point = item.mapToItem(overviewBackground, wheel.x, wheel.y);
        zoomAt(point.x, point.y, Math.pow(1.15, steps));
    }

    function zoomBy(factor) {
        cameraAnimated = true;
        zoomAt(overviewBackground.width / 2, overviewBackground.height / 2, factor);
    }

    function resetCamera() {
        cameraAnimated = true;
        cameraZoom = 1;
        cameraX = 0;
        cameraY = 0;
    }

    // Pans just enough to show a workspace that the camera left outside.
    function ensureVisible(id) {
        const cell = gridLayout.cells.find(c => c.id === id);
        if (!cell)
            return;

        const margin = Theme.spacingL;
        const left = workspaceGrid.x + cameraX + cell.x * cameraZoom;
        const top = workspaceGrid.y + cameraY + (cell.y - workspaceLabelSpace) * cameraZoom;
        const right = left + cell.width * cameraZoom;
        const bottom = workspaceGrid.y + cameraY + (cell.y + cell.height) * cameraZoom;

        let dx = 0;
        let dy = 0;
        if (left < margin)
            dx = margin - left;
        else if (right > overviewBackground.width - margin)
            dx = overviewBackground.width - margin - right;
        if (top < margin)
            dy = margin - top;
        else if (bottom > overviewBackground.height - margin)
            dy = overviewBackground.height - margin - bottom;

        if (dx !== 0 || dy !== 0) {
            cameraAnimated = true;
            setCamera(cameraZoom, cameraX + dx, cameraY + dy);
        }
    }

    onSelectedWorkspaceChanged: ensureVisible(selectedWorkspace)

    // Snaps the dragged workspace to the nearest free grid cell. A drop on
    // another workspace's cell is refused and the workspace goes back.
    function commitWorkspaceDrag() {
        const drag = dragPreview;
        dragPreview = null;
        if (!drag || !effectivePositions[drag.id])
            return;

        const stepX = Math.round(drag.dx / gridLayout.pitchX);
        const stepY = Math.round(drag.dy / gridLayout.pitchY);
        if (stepX === 0 && stepY === 0)
            return;

        const here = effectivePositions[drag.id];
        const target = [here[0] + stepX, here[1] + stepY];
        for (const key in effectivePositions) {
            const other = effectivePositions[key];
            if (Number(key) !== drag.id && Math.abs(other[0] - target[0]) < 0.5 && Math.abs(other[1] - target[1]) < 0.5)
                return;
        }

        const offsets = Object.assign({}, workspaceOffsets);
        const old = offsets[drag.id] || [0, 0];
        offsets[drag.id] = [old[0] + stepX, old[1] + stepY];
        workspaceOffsetsEdited(offsets);
    }

    // dotfiles: workspace reached from `fromId` in `direction`. Graph
    // connections win; otherwise the nearest workspace on screen.
    // Returns -1 when there is none.
    function neighborWorkspace(fromId, direction) {
        const linked = graphNodes[fromId]?.[direction];
        if (linked !== undefined && effectivePositions[linked] !== undefined)
            return linked;

        if (!effectivePositions[fromId])
            return displayedWorkspaceIds.length > 0 ? displayedWorkspaceIds[0] : -1;

        return spatialNeighbor(fromId, direction, []);
    }

    // dotfiles: workspace the selection would connect to in `direction`:
    // the nearest one on screen that is not linked to it yet, or -1 (then
    // a new workspace is created there).
    function connectTarget(fromId, direction) {
        return spatialNeighbor(fromId, direction, Object.values(graphNodes[fromId] || {}));
    }

    // dotfiles: nearest workspace on screen within a 45 degree cone of
    // `direction`, ignoring the ids in `skip`. Returns -1 when there is none.
    function spatialNeighbor(fromId, direction, skip) {
        const positions = effectivePositions;
        const here = positions[fromId];
        if (!here)
            return -1;

        const [dx, dy] = graphDirections[direction];
        let best = -1;
        let bestScore = Infinity;

        for (const key in positions) {
            const id = Number(key);
            if (id === fromId || skip.includes(id))
                continue;

            const [x, y] = positions[key];
            const primary = (x - here[0]) * dx + (y - here[1]) * dy;
            const secondary = Math.abs((x - here[0]) * dy) + Math.abs((y - here[1]) * dx);
            if (primary <= 0 || secondary > primary)
                continue;

            const score = primary + 2 * secondary;
            if (score < bestScore || (score === bestScore && id < best)) {
                best = id;
                bestScore = score;
            }
        }

        return best;
    }

    function getWorkspaceMonitorName(workspaceId) {
        if (!allWorkspaces || !workspaceId)
            return "";
        try {
            const ws = allWorkspaces.find(w => w?.id === workspaceId);
            return ws?.monitor?.name ?? "";
        } catch (e) {
            return "";
        }
    }

    function workspaceHasWindows(workspaceId) {
        if (!workspaceId)
            return false;
        try {
            const workspace = allWorkspaces.find(ws => ws?.id === workspaceId);
            if (!workspace)
                return false;
            const toplevels = workspace?.toplevels?.values || [];
            return toplevels.length > 0;
        } catch (e) {
            return false;
        }
    }

    function monitorIpcForWorkspace(workspaceId) {
        const workspace = allWorkspaces?.find(ws => ws?.id === workspaceId);
        return workspace?.monitor?.lastIpcObject ?? monitor?.lastIpcObject ?? null;
    }

    function monitorLogicalSize(ipc) {
        if (!ipc || !ipc.width || !ipc.height)
            return {
                "width": monitorPhysicalWidth,
                "height": monitorPhysicalHeight
            };

        const monScale = ipc.scale > 0 ? ipc.scale : 1;
        const rotated = ((ipc.transform ?? 0) % 2) === 1;
        return {
            "width": (rotated ? ipc.height : ipc.width) / monScale,
            "height": (rotated ? ipc.width : ipc.height) / monScale
        };
    }

    function cellForWorkspace(workspaceId) {
        const cell = gridLayout.cells.find(c => c.id === workspaceId);
        if (cell)
            return cell;
        return {
            "id": workspaceId,
            "x": 0,
            "y": 0,
            "width": workspaceImplicitWidth,
            "height": workspaceImplicitHeight
        };
    }

    function getWorkspaceViewportBounds(workspaceId, cellWidth, cellHeight) {
        const ipc = monitorIpcForWorkspace(workspaceId) ?? {};
        const logical = monitorLogicalSize(ipc);
        const reserved = ipc.reserved || [0, 0, 0, 0];

        const x = (ipc.x ?? 0) + (reserved[0] ?? 0);
        const y = (ipc.y ?? 0) + (reserved[1] ?? 0);
        const width = Math.max(logical.width - (reserved[0] ?? 0) - (reserved[2] ?? 0), 1);
        const height = Math.max(logical.height - (reserved[1] ?? 0) - (reserved[3] ?? 0), 1);

        return {
            "x": x,
            "y": y,
            "scale": Math.min(cellWidth / width, cellHeight / height)
        };
    }

    property bool monitorIsFocused: monitor?.focused ?? false
    // dotfiles: one uniform scale that fits the whole graph on screen.
    property real scale: {
        const points = Object.values(effectivePositions);
        if (points.length === 0)
            return SettingsData.overviewScale;

        const spanX = Math.max(...points.map(p => p[0])) - Math.min(...points.map(p => p[0]));
        const spanY = Math.max(...points.map(p => p[1])) - Math.min(...points.map(p => p[1]));
        const neededW = (spanX * (1 + graphGapRatio) + 1) * maxCellLogical.width + 20;
        const neededH = (spanY * (1 + graphGapRatio) + 1) * maxCellLogical.height + 20;

        return Math.min(maxGraphScale, availableWidth / neededW, availableHeight / neededH);
    }
    property color activeBorderColor: Theme.primary

    readonly property real monitorPhysicalWidth: panelWindow.screen ? (panelWindow.screen.width / root.dpr) : (monitor?.width ?? 1920)
    readonly property real monitorPhysicalHeight: panelWindow.screen ? (panelWindow.screen.height / root.dpr) : (monitor?.height ?? 1080)
    property real workspaceImplicitWidth: monitorPhysicalWidth * root.scale
    property real workspaceImplicitHeight: monitorPhysicalHeight * root.scale

    property int workspaceZ: 0
    property int windowZ: 1
    property int monitorLabelZ: 2
    property int windowDraggingZ: 99999
    property real workspaceSpacing: 5

    property int draggingFromWorkspace: -1
    property int draggingTargetWorkspace: -1

    // dotfiles: cells placed by graphPositions instead of a fixed grid.
    readonly property var gridLayout: {
        const ids = displayedWorkspaceIds;
        const positions = effectivePositions;
        const drag = dragPreview;
        if (!ids || ids.length === 0)
            return {
                "cells": [],
                "width": 0,
                "height": 0,
                "pitchX": 1,
                "pitchY": 1
            };

        const cellW = maxCellLogical.width * scale;
        const cellH = maxCellLogical.height * scale;
        const labelSpace = root.workspaceLabelSpace;
        const pitchX = cellW * (1 + graphGapRatio);
        const pitchY = cellH * (1 + graphGapRatio);

        const points = ids.map(id => positions[id] || [0, 0]);
        const minX = Math.min(...points.map(p => p[0]));
        const minY = Math.min(...points.map(p => p[1]));
        const maxX = Math.max(...points.map(p => p[0]));
        const maxY = Math.max(...points.map(p => p[1]));

        const cells = ids.map((id, index) => {
            const logical = monitorLogicalSize(monitorIpcForWorkspace(id));
            const width = logical.width * scale;
            const height = logical.height * scale;
            const dragged = drag && drag.id === id;
            const centerX = (points[index][0] - minX) * pitchX + cellW / 2 + (dragged ? drag.dx : 0);
            const centerY = labelSpace + (points[index][1] - minY) * pitchY + cellH / 2 + (dragged ? drag.dy : 0);
            return {
                "id": id,
                "x": centerX - width / 2,
                "y": centerY - height / 2,
                "width": width,
                "height": height
            };
        });

        return {
            "cells": cells,
            "width": (maxX - minX) * pitchX + cellW,
            "height": labelSpace + (maxY - minY) * pitchY + cellH,
            "pitchX": pitchX,
            "pitchY": pitchY
        };
    }

    // dotfiles: height reserved above each cell for its workspace number.
    readonly property real workspaceLabelSpace: Theme.fontSizeSmall * 1.8

    // dotfiles: undirected graph edges between shown workspaces.
    readonly property var graphEdges: {
        const edges = [];
        const seen = new Set();
        for (const key in graphNodes) {
            const id = Number(key);
            for (const direction in graphNodes[key]) {
                const target = graphNodes[key][direction];
                const edgeKey = Math.min(id, target) + "-" + Math.max(id, target);
                if (target !== id && !seen.has(edgeKey)) {
                    seen.add(edgeKey);
                    edges.push([id, target]);
                }
            }
        }
        return edges;
    }

    implicitWidth: overviewBackground.implicitWidth + Theme.spacingL * 2
    implicitHeight: overviewBackground.implicitHeight + Theme.spacingL * 2

    Component.onCompleted: {
        Hyprland.refreshToplevels();
        Hyprland.refreshWorkspaces();
        Hyprland.refreshMonitors();
        resetSelection();
        previousWorkspaceIds = displayedWorkspaceIds;
    }

    onOverviewOpenChanged: {
        if (overviewOpen) {
            Hyprland.refreshToplevels();
            Hyprland.refreshWorkspaces();
            Hyprland.refreshMonitors();
            resetSelection();
        }
    }

    Rectangle {
        id: overviewBackground
        property real padding: 10
        anchors.fill: parent
        anchors.margins: Theme.spacingL

        implicitWidth: workspaceGrid.implicitWidth + padding * 2
        implicitHeight: workspaceGrid.implicitHeight + padding * 2
        radius: Theme.cornerRadius
        color: Theme.surfaceContainer
        // dotfiles: zoomed content stays inside the panel.
        clip: true

        // dotfiles: below the graph layers: the wheel zooms around the
        // pointer and a middle-button drag pans (over a window thumbnail
        // the middle button still closes the window).
        MouseArea {
            id: cameraArea
            anchors.fill: parent
            acceptedButtons: Qt.MiddleButton

            property point pressPoint
            property real startX: 0
            property real startY: 0

            onWheel: wheel => root.wheelZoom(wheel, cameraArea)

            onPressed: mouse => {
                root.cameraAnimated = false;
                pressPoint = Qt.point(mouse.x, mouse.y);
                startX = root.cameraX;
                startY = root.cameraY;
            }

            onPositionChanged: mouse => root.setCamera(root.cameraZoom, startX + mouse.x - pressPoint.x, startY + mouse.y - pressPoint.y)
        }

        // dotfiles: rename / icon editor (R / I), outside the camera.
        Rectangle {
            id: editorBar
            opacity: root.editingWorkspace > 0 ? 1 : 0
            visible: opacity > 0
            z: 10
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Theme.spacingM
            width: editorRow.implicitWidth + Theme.spacingM * 2
            height: editorRow.implicitHeight + Theme.spacingS * 2
            radius: Theme.cornerRadius
            color: Theme.surfaceContainerHigh
            border.width: 1
            border.color: root.activeBorderColor

            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.shortDuration
                    easing.type: Theme.standardEasing
                }
            }

            Row {
                id: editorRow
                anchors.centerIn: parent
                spacing: Theme.spacingS

                DankIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.editingField === "icon" && editorInput.text.length > 0
                    name: editorInput.text
                    size: Theme.fontSizeLarge
                    color: Theme.surfaceText
                }

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: (root.editingField === "name" ? "Nombre del workspace " : "Icono (Material Symbols) del workspace ") + root.editingWorkspace + ":"
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.surfaceText
                }

                TextInput {
                    id: editorInput
                    anchors.verticalCenter: parent.verticalCenter
                    width: 220
                    maximumLength: root.editingField === "name" ? 32 : 48
                    color: Theme.surfaceText
                    selectionColor: root.activeBorderColor
                    font.pixelSize: Theme.fontSizeMedium
                    clip: true

                    Keys.onReturnPressed: event => {
                        root.finishEditing(true);
                        event.accepted = true;
                    }
                    Keys.onEnterPressed: event => {
                        root.finishEditing(true);
                        event.accepted = true;
                    }
                    Keys.onEscapePressed: event => {
                        root.finishEditing(false);
                        event.accepted = true;
                    }
                }

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Enter guarda · Esc cancela · vacío borra"
                    font.pixelSize: Theme.fontSizeSmall
                    color: Theme.withAlpha(Theme.surfaceText, 0.6)
                }
            }
        }

        ElevationShadow {
            anchors.fill: parent
            z: -1
            level: Theme.elevationLevel2
            fallbackOffset: 4
            targetRadius: Theme.cornerRadius
            targetColor: Theme.surfaceContainer
            shadowOpacity: Theme.elevationLevel2 && Theme.elevationLevel2.alpha !== undefined ? Theme.elevationLevel2.alpha : 0.25
            shadowEnabled: Theme.elevationEnabled
        }

        // dotfiles: graph connections, from border to border of each cell.
        Canvas {
            id: edgeCanvas
            anchors.centerIn: parent
            transform: [CameraScale {}, CameraTranslate {}]
            width: root.gridLayout.width
            height: root.gridLayout.height
            z: root.workspaceZ

            onPaint: {
                const ctx = getContext("2d");
                ctx.reset();
                ctx.strokeStyle = Theme.outline;
                ctx.lineWidth = 2;

                const cells = {};
                for (const cell of root.gridLayout.cells)
                    cells[cell.id] = cell;

                for (const [a, b] of root.graphEdges) {
                    const from = cells[a];
                    const to = cells[b];
                    if (!from || !to)
                        continue;

                    const ax = from.x + from.width / 2;
                    const ay = from.y + from.height / 2;
                    const dx = to.x + to.width / 2 - ax;
                    const dy = to.y + to.height / 2 - ay;

                    // Fraction of the segment hidden inside a cell.
                    const inside = cell => Math.min(dx !== 0 ? cell.width / 2 / Math.abs(dx) : Infinity, dy !== 0 ? cell.height / 2 / Math.abs(dy) : Infinity);
                    const start = inside(from);
                    const end = 1 - inside(to);
                    if (end <= start)
                        continue;

                    ctx.beginPath();
                    ctx.moveTo(ax + dx * start, ay + dy * start);
                    ctx.lineTo(ax + dx * end, ay + dy * end);
                    ctx.stroke();
                }
            }

            Connections {
                target: root
                function onGridLayoutChanged() {
                    edgeCanvas.requestPaint();
                }
                function onGraphEdgesChanged() {
                    edgeCanvas.requestPaint();
                }
            }
        }

        Item {
            id: workspaceGrid

            z: root.workspaceZ
            anchors.centerIn: parent
            transform: [CameraScale {}, CameraTranslate {}]
            implicitWidth: root.gridLayout.width
            implicitHeight: root.gridLayout.height

            Repeater {
                model: root.gridLayout.cells.length

                Rectangle {
                    id: workspace
                    required property int index
                    readonly property var cell: root.gridLayout.cells[index] ?? null
                    property int workspaceValue: cell?.id ?? -1
                    property bool workspaceExists: (root.allWorkspaceIds && workspaceValue > 0) ? root.allWorkspaceIds.includes(workspaceValue) : false
                    property var workspaceObj: (workspaceExists && Hyprland.workspaces?.values) ? Hyprland.workspaces.values.find(ws => ws?.id === workspaceValue) : null
                    property bool isActive: workspaceObj?.active ?? false
                    property bool isOnThisMonitor: (workspaceObj && root.monitor) ? (workspaceObj.monitor?.name === root.monitor.name) : true
                    property bool hasWindows: (workspaceValue > 0) ? root.workspaceHasWindows(workspaceValue) : false
                    // dotfiles: graph workspaces that do not exist yet are transparent boxes.
                    property color defaultWorkspaceColor: workspaceExists ? Theme.surfaceContainer : "transparent"
                    property color hoveredWorkspaceColor: Qt.lighter(defaultWorkspaceColor, 1.1)
                    property color hoveredBorderColor: Theme.surfaceVariant
                    property bool hoveredWhileDragging: false
                    property bool shouldShowActiveIndicator: isActive && isOnThisMonitor && hasWindows
                    property bool isSelected: workspaceValue === root.selectedWorkspace
                    property bool isDragged: root.dragPreview !== null && root.dragPreview.id === workspaceValue

                    visible: workspaceValue !== -1
                    z: isDragged ? 1 : 0
                    opacity: isDragged ? 0.8 : 1

                    x: cell?.x ?? 0
                    y: cell?.y ?? 0
                    width: cell?.width ?? 0
                    height: cell?.height ?? 0
                    color: (hoveredWhileDragging || (isSelected && workspaceExists)) ? hoveredWorkspaceColor : defaultWorkspaceColor
                    radius: Theme.cornerRadius
                    // dotfiles: the selection gets a thicker border than the active
                    // one; workspaces that do not exist yet keep a thin outline.
                    border.width: isSelected ? 4 : (shouldShowActiveIndicator ? 2 : 1.5)
                    border.color: {
                        if (hoveredWhileDragging)
                            return hoveredBorderColor;
                        if (isSelected || shouldShowActiveIndicator)
                            return root.activeBorderColor;
                        if (!workspaceExists)
                            return Theme.withAlpha(Theme.outline, 0.7);
                        return Theme.withAlpha(root.activeBorderColor, 0);
                    }

                    // dotfiles: the selection moves with a short transition.
                    Behavior on border.width {
                        NumberAnimation {
                            duration: Theme.shortDuration
                            easing.type: Theme.standardEasing
                        }
                    }

                    Behavior on border.color {
                        ColorAnimation {
                            duration: Theme.shortDuration
                            easing.type: Theme.standardEasing
                        }
                    }

                    // dotfiles: small label outside the top-left corner: the number,
                    // then the optional icon and name.
                    Row {
                        id: workspaceLabel
                        readonly property var info: root.workspaceMetadata[workspace.workspaceValue] ?? null
                        readonly property color labelColor: workspace.isSelected ? root.activeBorderColor : Theme.withAlpha(Theme.surfaceText, 0.7)

                        anchors.left: parent.left
                        anchors.bottom: parent.top
                        anchors.leftMargin: Theme.spacingXS
                        anchors.bottomMargin: 2
                        spacing: Theme.spacingXS

                        StyledText {
                            text: workspace.workspaceValue
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: workspace.isSelected ? Font.Bold : Font.Medium
                            color: workspaceLabel.labelColor
                        }

                        DankIcon {
                            visible: !!workspaceLabel.info?.icon
                            anchors.verticalCenter: parent.verticalCenter
                            name: workspaceLabel.info?.icon ?? ""
                            size: Theme.fontSizeSmall + 2
                            color: workspaceLabel.labelColor
                        }

                        StyledText {
                            visible: !!workspaceLabel.info?.name
                            text: workspaceLabel.info?.name ?? ""
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: workspace.isSelected ? Font.Bold : Font.Medium
                            color: workspaceLabel.labelColor
                        }
                    }

                    // dotfiles: press selects; releasing after a small movement is a
                    // click (activate), a larger movement drags the workspace.
                    MouseArea {
                        id: workspaceArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        preventStealing: true
                        onWheel: wheel => root.wheelZoom(wheel, workspaceArea)

                        property point pressPoint
                        property bool dragging: false

                        onPressed: mouse => {
                            pressPoint = mapToItem(workspaceGrid, mouse.x, mouse.y);
                            dragging = false;
                            root.selectedWorkspace = workspace.workspaceValue;
                        }

                        onPositionChanged: mouse => {
                            const point = mapToItem(workspaceGrid, mouse.x, mouse.y);
                            const dx = point.x - pressPoint.x;
                            const dy = point.y - pressPoint.y;
                            if (!dragging && Math.hypot(dx, dy) < Qt.styleHints.startDragDistance)
                                return;
                            dragging = true;
                            root.dragPreview = {
                                "id": workspace.workspaceValue,
                                "dx": dx,
                                "dy": dy
                            };
                        }

                        onReleased: {
                            if (dragging) {
                                dragging = false;
                                root.commitWorkspaceDrag();
                            } else if (containsMouse && root.draggingTargetWorkspace === -1) {
                                // Activate before closing: closing destroys this widget.
                                root.activateWorkspace(workspace.workspaceValue);
                                root.closeRequested();
                            }
                        }

                        onCanceled: {
                            dragging = false;
                            root.dragPreview = null;
                        }
                    }

                    DropArea {
                        anchors.fill: parent
                        onEntered: {
                            root.draggingTargetWorkspace = workspace.workspaceValue;
                            if (root.draggingFromWorkspace == root.draggingTargetWorkspace)
                                return;
                            workspace.hoveredWhileDragging = true;
                        }
                        onExited: {
                            workspace.hoveredWhileDragging = false;
                            if (root.draggingTargetWorkspace == workspace.workspaceValue)
                                root.draggingTargetWorkspace = -1;
                        }
                    }
                }
            }
        }

        Item {
            id: windowSpace
            anchors.centerIn: parent
            transform: [CameraScale {}, CameraTranslate {}]
            implicitWidth: workspaceGrid.implicitWidth
            implicitHeight: workspaceGrid.implicitHeight

            Repeater {
                model: ScriptModel {
                    values: {
                        const workspaces = root.allWorkspaces;
                        const shown = new Set(root.displayedWorkspaceIds);

                        if (!workspaces || workspaces.length === 0)
                            return [];

                        try {
                            const result = [];
                            for (const workspace of workspaces) {
                                const wsId = workspace?.id ?? -1;
                                if (shown.has(wsId)) {
                                    const toplevels = workspace?.toplevels?.values || [];
                                    for (const toplevel of toplevels) {
                                        result.push(toplevel);
                                    }
                                }
                            }
                            return result;
                        } catch (e) {
                            log.error("OverviewWidget filter error:", e);
                            return [];
                        }
                    }
                }
                delegate: OverviewWindow {
                    id: window
                    required property var modelData

                    overviewOpen: root.overviewOpen
                    readonly property int windowWorkspaceId: modelData?.workspace?.id ?? -1
                    readonly property var workspaceCell: root.cellForWorkspace(windowWorkspaceId)
                    readonly property var workspaceBounds: root.getWorkspaceViewportBounds(windowWorkspaceId, workspaceCell.width, workspaceCell.height)

                    toplevel: modelData
                    scale: root.scale
                    monitorDpr: root.dpr
                    availableWorkspaceWidth: workspaceCell.width
                    availableWorkspaceHeight: workspaceCell.height
                    contentOriginX: workspaceBounds.x
                    contentOriginY: workspaceBounds.y
                    contentScale: workspaceBounds.scale
                    widgetMonitorId: root.monitor.id

                    xOffset: workspaceCell.x
                    yOffset: workspaceCell.y

                    z: atInitPosition ? root.windowZ : root.windowDraggingZ
                    property bool atInitPosition: (initX == x && initY == y)

                    Drag.hotSpot.x: width / 2
                    Drag.hotSpot.y: height / 2

                    MouseArea {
                        id: dragArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: window.hovered = true
                        onExited: window.hovered = false
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                        drag.target: parent
                        // dotfiles: the wheel zooms the overview.
                        onWheel: wheel => root.wheelZoom(wheel, dragArea)

                        onPressed: mouse => {
                            root.draggingFromWorkspace = windowData?.workspace.id;
                            window.pressed = true;
                            window.Drag.active = true;
                            window.Drag.source = window;
                            window.Drag.hotSpot.x = mouse.x;
                            window.Drag.hotSpot.y = mouse.y;
                        }

                        onReleased: {
                            const targetWorkspace = root.draggingTargetWorkspace;
                            window.pressed = false;
                            window.Drag.active = false;
                            root.draggingFromWorkspace = -1;
                            root.draggingTargetWorkspace = -1;

                            if (targetWorkspace !== -1 && targetWorkspace !== windowData?.workspace.id) {
                                HyprlandService.moveToWorkspace(targetWorkspace, windowData?.address, false);
                                Qt.callLater(() => {
                                    Hyprland.refreshToplevels();
                                    Hyprland.refreshWorkspaces();
                                    Qt.callLater(() => {
                                        window.x = window.initX;
                                        window.y = window.initY;
                                    });
                                });
                            } else {
                                window.x = window.initX;
                                window.y = window.initY;
                            }
                        }

                        onClicked: event => {
                            if (!windowData || !windowData.address)
                                return;
                            if (event.button === Qt.LeftButton) {
                                HyprlandService.focusWindow(windowData.address);
                                root.closeRequested();
                                event.accepted = true;
                            } else if (event.button === Qt.MiddleButton) {
                                HyprlandService.closeWindow(windowData.address);
                                event.accepted = true;
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: monitorLabelSpace
            anchors.centerIn: parent
            transform: [CameraScale {}, CameraTranslate {}]
            implicitWidth: workspaceGrid.implicitWidth
            implicitHeight: workspaceGrid.implicitHeight
            z: root.monitorLabelZ

            Repeater {
                model: root.gridLayout.cells.length
                delegate: Item {
                    id: labelItem
                    required property int index
                    readonly property var cell: root.gridLayout.cells[index] ?? null
                    property int workspaceValue: cell?.id ?? -1
                    property bool workspaceExists: (root.allWorkspaceIds && workspaceValue > 0) ? root.allWorkspaceIds.includes(workspaceValue) : false
                    property string workspaceMonitorName: (workspaceValue > 0) ? root.getWorkspaceMonitorName(workspaceValue) : ""

                    x: cell?.x ?? 0
                    y: cell?.y ?? 0
                    width: cell?.width ?? 0
                    height: cell?.height ?? 0

                    Rectangle {
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.spacingS
                        width: monitorNameText.contentWidth + Theme.spacingS * 2
                        height: monitorNameText.contentHeight + Theme.spacingXS * 2
                        radius: Theme.cornerRadius
                        color: Theme.surface
                        visible: labelItem.workspaceExists && labelItem.workspaceMonitorName !== ""

                        StyledText {
                            id: monitorNameText
                            anchors.centerIn: parent
                            text: labelItem.workspaceMonitorName
                            font.pixelSize: Theme.fontSizeSmall
                            font.weight: Font.Medium
                            color: Theme.surfaceText
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
    }
}
