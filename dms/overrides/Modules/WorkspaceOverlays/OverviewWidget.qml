import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.Common
import qs.Services
import qs.Widgets

Item {
    id: root
    readonly property var log: Log.scoped("OverviewWidget")
    required property var panelWindow
    required property bool overviewOpen
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

    // dotfiles: workspace graph persisted by hypr/modules/workspaces.lua
    // ({"3": {"left": 2, "right": 4}, ...}).
    property var workspaceGraph: ({})

    FileView {
        path: Quickshell.env("HOME") + "/.local/state/hyprland/workspace-graph.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                root.workspaceGraph = JSON.parse(text()) || {};
            } catch (e) {
                root.workspaceGraph = {};
            }
        }
        onLoadFailed: root.workspaceGraph = {}
    }

    function resetSelection() {
        selectedWorkspace = monitor?.activeWorkspace?.id ?? (displayedWorkspaceIds[0] ?? -1);
    }

    // -- dotfiles: graph layout -----------------------------------------
    // Port of the earlier GTK viewer's layout (git history): the active
    // workspace sits at (0, 0), its component expands around it by BFS
    // over left/right/up/down, and disconnected components go to the side
    // that keeps the largest scale.

    readonly property var graphDirections: ({
            "left": [-1, 0],
            "right": [1, 0],
            "up": [0, -1],
            "down": [0, 1]
        })
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

    function nearestFreeCell(cell, taken) {
        for (let radius = 1;; radius++) {
            for (let dx = -radius; dx <= radius; dx++) {
                for (let dy = -radius; dy <= radius; dy++) {
                    if (Math.max(Math.abs(dx), Math.abs(dy)) !== radius)
                        continue;
                    if (!taken.has((cell[0] + dx) + "," + (cell[1] + dy)))
                        return [cell[0] + dx, cell[1] + dy];
                }
            }
        }
    }

    function layoutComponent(nodes, rootId, visited) {
        const positions = {};
        const taken = new Set(["0,0"]);
        const queue = [rootId];
        const ids = Object.keys(nodes).map(Number).sort((a, b) => a - b);

        positions[rootId] = [0, 0];
        visited.add(rootId);

        const place = (id, cell) => {
            if (taken.has(cell[0] + "," + cell[1]))
                cell = nearestFreeCell(cell, taken);
            positions[id] = cell;
            taken.add(cell[0] + "," + cell[1]);
            visited.add(id);
            queue.push(id);
        };

        while (queue.length > 0) {
            const current = queue.shift();
            const [cx, cy] = positions[current];

            for (const direction of Object.keys(nodes[current]).sort()) {
                const target = nodes[current][direction];
                if (visited.has(target))
                    continue;
                const [dx, dy] = graphDirections[direction];
                place(target, [cx + dx, cy + dy]);
            }

            // Also follow connections declared only on the other side.
            for (const other of ids) {
                if (visited.has(other))
                    continue;
                const links = nodes[other];
                const direction = Object.keys(links).find(d => links[d] === current);
                if (direction === undefined)
                    continue;
                const [dx, dy] = graphDirections[direction];
                place(other, [cx - dx, cy - dy]);
            }
        }

        return positions;
    }

    function layoutGraph(nodes, center, aspect, cellAspect) {
        const ids = Object.keys(nodes).map(Number).sort((a, b) => a - b);
        if (ids.length === 0)
            return {};
        if (nodes[center] === undefined)
            center = ids[0];

        const visited = new Set();
        const positions = layoutComponent(nodes, center, visited);
        const pitchX = 1 + graphGapRatio;
        const pitchY = cellAspect * (1 + graphGapRatio);

        // Relative scale a bounding box allows, in units of one cell width.
        const relativeScale = (xs, ys) => Math.min(aspect / ((Math.max(...xs) - Math.min(...xs)) * pitchX + 1), 1 / ((Math.max(...ys) - Math.min(...ys)) * pitchY + cellAspect));

        for (const rootId of ids) {
            if (visited.has(rootId))
                continue;

            const comp = layoutComponent(nodes, rootId, visited);
            const points = Object.values(comp);
            const minX = Math.min(...points.map(p => p[0]));
            const minY = Math.min(...points.map(p => p[1]));
            const compW = Math.max(...points.map(p => p[0])) - minX + 1;
            const compH = Math.max(...points.map(p => p[1])) - minY + 1;

            const placed = Object.values(positions);
            const xs = placed.map(p => p[0]);
            const ys = placed.map(p => p[1]);
            const midX = -(compW - 1) / 2;
            const midY = -(compH - 1) / 2;

            // Right, left, below, above; the first wins on ties.
            const offsets = [[Math.max(...xs) + 1 + componentGap, midY], [Math.min(...xs) - componentGap - compW, midY], [midX, Math.max(...ys) + 1 + componentGap], [midX, Math.min(...ys) - componentGap - compH]];

            let best = offsets[0];
            let bestScore = -1;
            for (const offset of offsets) {
                const score = relativeScale(xs.concat([offset[0], offset[0] + compW - 1]), ys.concat([offset[1], offset[1] + compH - 1]));
                if (score > bestScore) {
                    best = offset;
                    bestScore = score;
                }
            }

            for (const key in comp)
                positions[key] = [comp[key][0] - minX + best[0], comp[key][1] - minY + best[1]];
        }

        return positions;
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

    readonly property var graphPositions: layoutGraph(graphNodes, monitor?.activeWorkspace?.id ?? -1, availableWidth / availableHeight, maxCellLogical.height / maxCellLogical.width)

    // dotfiles: workspace reached from `fromId` in `direction`. Graph
    // connections win; otherwise the nearest workspace on screen within a
    // 45 degree cone of the direction. Returns -1 when there is none.
    function neighborWorkspace(fromId, direction) {
        const positions = graphPositions;
        const linked = graphNodes[fromId]?.[direction];
        if (linked !== undefined && positions[linked] !== undefined)
            return linked;

        const here = positions[fromId];
        if (!here)
            return displayedWorkspaceIds.length > 0 ? displayedWorkspaceIds[0] : -1;

        const [dx, dy] = graphDirections[direction];
        let best = -1;
        let bestScore = Infinity;

        for (const key in positions) {
            const id = Number(key);
            if (id === fromId)
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
        const points = Object.values(graphPositions);
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
        const positions = graphPositions;
        if (!ids || ids.length === 0)
            return {
                "cells": [],
                "width": 0,
                "height": 0
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
            const centerX = (points[index][0] - minX) * pitchX + cellW / 2;
            const centerY = labelSpace + (points[index][1] - minY) * pitchY + cellH / 2;
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
            "height": labelSpace + (maxY - minY) * pitchY + cellH
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

                    visible: workspaceValue !== -1

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

                    // dotfiles: small workspace number outside the top-left corner.
                    StyledText {
                        anchors.left: parent.left
                        anchors.bottom: parent.top
                        anchors.leftMargin: Theme.spacingXS
                        anchors.bottomMargin: 2
                        text: workspace.workspaceValue
                        font.pixelSize: Theme.fontSizeSmall
                        font.weight: workspace.isSelected ? Font.Bold : Font.Medium
                        color: workspace.isSelected ? root.activeBorderColor : Theme.withAlpha(Theme.surfaceText, 0.7)
                    }

                    MouseArea {
                        id: workspaceArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onClicked: {
                            if (root.draggingTargetWorkspace === -1) {
                                root.overviewOpen = false;
                                HyprlandService.focusWorkspace(workspace.workspaceValue);
                            }
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
                                root.overviewOpen = false;
                                HyprlandService.focusWindow(windowData.address);
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
