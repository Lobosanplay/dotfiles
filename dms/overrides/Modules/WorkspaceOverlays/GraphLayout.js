.pragma library

// dotfiles: pure graph layout for the workspace overview (no QML, no
// Quickshell), so it can be tested outside a graphical session
// (tests/layout). Same input, same output: no randomness, ids and
// directions are always visited in sorted order.
//
// nodes: {id: {"left": id, "right": id, "up": id, "down": id}}
// Returns {id: [x, y]} in grid cells, `center` at [0, 0].

var DIRECTIONS = {
    "left": [-1, 0],
    "right": [1, 0],
    "up": [0, -1],
    "down": [0, 1]
};

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
            const [dx, dy] = DIRECTIONS[direction];
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
            const [dx, dy] = DIRECTIONS[direction];
            place(other, [cx - dx, cy - dy]);
        }
    }

    return positions;
}

// gapRatio: gap between cells relative to a cell; componentGap: extra
// grid cells between disconnected components.
function layoutGraph(nodes, center, aspect, cellAspect, gapRatio, componentGap) {
    const ids = Object.keys(nodes).map(Number).sort((a, b) => a - b);
    if (ids.length === 0)
        return {};
    if (nodes[center] === undefined)
        center = ids[0];

    const visited = new Set();
    const positions = layoutComponent(nodes, center, visited);
    const pitchX = 1 + gapRatio;
    const pitchY = cellAspect * (1 + gapRatio);

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
