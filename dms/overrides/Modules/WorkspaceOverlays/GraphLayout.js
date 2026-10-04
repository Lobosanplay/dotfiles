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

function cellKey(cell) {
    return cell[0] + "," + cell[1];
}

// True if segments a-b and c-d cross at a point that is not a shared end.
function segmentsCross(a, b, c, d) {
    if (cellKey(a) === cellKey(c) || cellKey(a) === cellKey(d) || cellKey(b) === cellKey(c) || cellKey(b) === cellKey(d))
        return false;

    const side = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
    const s1 = side(a, b, c);
    const s2 = side(a, b, d);
    const s3 = side(c, d, a);
    const s4 = side(c, d, b);

    return s1 !== 0 && s2 !== 0 && s3 !== 0 && s4 !== 0 && s1 !== s2 && s3 !== s4;
}

// True if the segment from a to b runs over another occupied cell.
function passesThrough(a, b, taken) {
    const steps = Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) * 4;

    for (let i = 1; i < steps; i++) {
        const t = i / steps;
        const cell = [Math.round(a[0] + (b[0] - a[0]) * t), Math.round(a[1] + (b[1] - a[1]) * t)];
        const key = cellKey(cell);
        if (key !== cellKey(a) && key !== cellKey(b) && taken.has(key))
            return true;
    }

    return false;
}

// Weights for choosing a cell when the ideal one is taken (see chooseCell).
var LAYOUT_WEIGHTS = {
    "wrongSide": 500,
    "crossing": 100,
    "overNode": 60,
    "diagonal": 25,
    "distance": 1
};

// Cost of putting a node at `cell`, given the cells of its neighbors that
// are already placed and the direction each connection has: crossings with
// placed edges, edges running over other cells, edges that leave their
// line (diagonals) and edge length. A cell on the wrong side of a
// connection (e.g. not above for "up") costs the most: it would misstate
// the graph.
function placementCost(cell, links, taken, edges, weights) {
    let cost = 0;

    for (const [other, d] of links) {
        const along = (cell[0] - other[0]) * d[0] + (cell[1] - other[1]) * d[1];
        const diagonal = d[0] !== 0 ? cell[1] !== other[1] : cell[0] !== other[0];
        let crossings = 0;
        for (const [a, b] of edges) {
            if (segmentsCross(other, cell, a, b))
                crossings++;
        }

        cost += (along <= 0 ? weights.wrongSide : 0)
            + crossings * weights.crossing
            + (passesThrough(other, cell, taken) ? weights.overNode : 0)
            + (diagonal ? weights.diagonal : 0)
            + (Math.abs(cell[0] - other[0]) + Math.abs(cell[1] - other[1])) * weights.distance;
    }

    return cost;
}

// The ideal cell next to `parent` in direction `d` is taken: score cells
// further along the same line, cells shifted sideways and the ring around
// the ideal cell. `links` are [cell, direction] pairs from every placed
// neighbor (the parent included). Ties keep the candidate order, so the
// result is deterministic. Falls back to the nearest free cell.
function chooseCell(parent, d, links, taken, edges, weights) {
    const ideal = [parent[0] + d[0], parent[1] + d[1]];
    const sideways = [Math.abs(d[1]), Math.abs(d[0])];
    const candidates = [];

    for (let k = 2; k <= 3; k++)
        candidates.push([parent[0] + d[0] * k, parent[1] + d[1] * k]);
    for (const k of [1, -1, 2, -2])
        candidates.push([ideal[0] + sideways[0] * k, ideal[1] + sideways[1] * k]);
    for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
            if (dx !== 0 || dy !== 0)
                candidates.push([ideal[0] + dx, ideal[1] + dy]);
        }
    }

    let best = null;
    let bestScore = Infinity;

    for (const cell of candidates) {
        if (taken.has(cellKey(cell)))
            continue;

        const score = placementCost(cell, links, taken, edges, weights);
        if (score < bestScore) {
            best = cell;
            bestScore = score;
        }
    }

    return best || nearestFreeCell(ideal, taken);
}

function layoutComponent(nodes, rootId, visited, weights) {
    const positions = {};
    const taken = new Set(["0,0"]);
    const edges = [];
    const queue = [rootId];
    const ids = Object.keys(nodes).map(Number).sort((a, b) => a - b);

    positions[rootId] = [0, 0];
    visited.add(rootId);

    // Places `id` next to `parent` in direction `d` (or the best free cell
    // when that one is taken) and records its edges to placed neighbors.
    const place = (id, parent, d) => {
        // Every placed neighbor, with the direction from it towards `id`.
        const links = [];
        for (const direction of Object.keys(nodes[id] || {}).sort()) {
            const neighbor = positions[nodes[id][direction]];
            const [dx, dy] = DIRECTIONS[direction];
            if (neighbor)
                links.push([neighbor, [-dx, -dy]]);
        }
        if (!links.some(([cell]) => cellKey(cell) === cellKey(parent)))
            links.push([parent, d]);

        const ideal = [parent[0] + d[0], parent[1] + d[1]];
        const cell = taken.has(cellKey(ideal)) ? chooseCell(parent, d, links, taken, edges, weights || LAYOUT_WEIGHTS) : ideal;
        positions[id] = cell;
        taken.add(cellKey(cell));
        for (const [other] of links)
            edges.push([other, cell]);
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
            place(target, [cx, cy], DIRECTIONS[direction]);
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
            place(other, [cx, cy], [-dx, -dy]);
        }
    }

    return positions;
}

// gapRatio: gap between cells relative to a cell; componentGap: extra
// grid cells between disconnected components.
function layoutGraph(nodes, center, aspect, cellAspect, gapRatio, componentGap, weights) {
    const ids = Object.keys(nodes).map(Number).sort((a, b) => a - b);
    if (ids.length === 0)
        return {};
    if (nodes[center] === undefined)
        center = ids[0];

    const visited = new Set();
    const positions = layoutComponent(nodes, center, visited, weights);
    const pitchX = 1 + gapRatio;
    const pitchY = cellAspect * (1 + gapRatio);

    // Relative scale a bounding box allows, in units of one cell width.
    const relativeScale = (xs, ys) => Math.min(aspect / ((Math.max(...xs) - Math.min(...xs)) * pitchX + 1), 1 / ((Math.max(...ys) - Math.min(...ys)) * pitchY + cellAspect));

    for (const rootId of ids) {
        if (visited.has(rootId))
            continue;

        const comp = layoutComponent(nodes, rootId, visited, weights);
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

// Uniform scale that fits every position on screen: cells of
// cellWidth x cellHeight (logical px at scale 1), spaced by gapRatio,
// inside availableWidth x availableHeight, at most maxScale. Returns null
// when there is nothing to lay out.
function fitScale(positions, availableWidth, availableHeight, cellWidth, cellHeight, gapRatio, maxScale) {
    const points = Object.values(positions);
    if (points.length === 0)
        return null;

    const spanX = Math.max(...points.map(p => p[0])) - Math.min(...points.map(p => p[0]));
    const spanY = Math.max(...points.map(p => p[1])) - Math.min(...points.map(p => p[1]));
    const neededW = (spanX * (1 + gapRatio) + 1) * cellWidth + 20;
    const neededH = (spanY * (1 + gapRatio) + 1) * cellHeight + 20;

    return Math.min(maxScale, availableWidth / neededW, availableHeight / neededH);
}
