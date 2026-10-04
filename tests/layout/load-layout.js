// Loads the overview's real GraphLayout.js (a QML ".pragma library" file)
// into a plain Node context, so the layout is tested without Quickshell
// or a graphical session.

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const file = path.join(__dirname, "../../dms/overrides/Modules/WorkspaceOverlays/GraphLayout.js");

function loadLayout() {
    // ".pragma library" is a QML directive, not JavaScript.
    const source = fs.readFileSync(file, "utf8").replace(/^\.pragma library\s*$/m, "");
    const context = {};
    vm.runInNewContext(source, context, { filename: file });

    // Values created inside the vm context have their own Array/Object
    // prototypes; plain copies compare correctly with deepStrictEqual.
    const plain = value => (value === null || value === undefined ? value : JSON.parse(JSON.stringify(value)));
    return {
        DIRECTIONS: plain(context.DIRECTIONS),
        LAYOUT_WEIGHTS: plain(context.LAYOUT_WEIGHTS),
        layoutGraph: (...args) => plain(context.layoutGraph(...args)),
        fitScale: (...args) => context.fitScale(...args),
    };
}

const OPPOSITE = { left: "right", right: "left", up: "down", down: "up" };
const VECTOR = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };

// Graph like workspace-graph.json from [a, direction, b] links (both ends).
function graph(ids, links) {
    const nodes = {};
    for (const id of ids)
        nodes[id] = {};
    for (const [a, direction, b] of links) {
        nodes[a][direction] = b;
        nodes[b][OPPOSITE[direction]] = a;
    }
    return nodes;
}

// Same graph, with object keys inserted in a different order (as another
// JSON file could list them).
function reordered(nodes) {
    const result = {};
    for (const id of Object.keys(nodes).reverse()) {
        result[id] = {};
        for (const direction of Object.keys(nodes[id]).reverse())
            result[id][direction] = nodes[id][direction];
    }
    return result;
}

module.exports = { loadLayout, graph, reordered, OPPOSITE, VECTOR };
