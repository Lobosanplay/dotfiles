// Layout quality on many generated graphs: guards against regressions in
// how collisions are resolved. node --test tests/layout

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadLayout, OPPOSITE, VECTOR } = require("./load-layout.js");

const Layout = loadLayout();
const DIRECTIONS = Object.keys(OPPOSITE);

// Deterministic pseudo-random numbers (no Math.random: same graphs every run).
function random(seed) {
    return () => {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        return seed / 2147483648;
    };
}

// Grows a graph like SUPER+ALT+arrows does (a new workspace in a free
// direction of an existing one), then adds `extra` connections between
// existing workspaces like SUPER+SHIFT+arrow, which creates cycles.
function generate(size, seed, extra) {
    const next = random(seed);
    const nodes = { 1: {} };

    for (let id = 2; id <= size; id++) {
        for (let attempt = 0; attempt < 50; attempt++) {
            const ids = Object.keys(nodes).map(Number);
            const from = ids[Math.floor(next() * ids.length)];
            const direction = DIRECTIONS[Math.floor(next() * 4)];
            if (!nodes[from][direction]) {
                nodes[id] = { [OPPOSITE[direction]]: from };
                nodes[from][direction] = id;
                break;
            }
        }
    }

    for (let k = 0; k < extra; k++) {
        const ids = Object.keys(nodes).map(Number);
        const a = ids[Math.floor(next() * ids.length)];
        const b = ids[Math.floor(next() * ids.length)];
        const direction = DIRECTIONS[Math.floor(next() * 4)];
        if (a !== b && !nodes[a][direction] && !nodes[b][OPPOSITE[direction]] && !Object.values(nodes[a]).includes(b)) {
            nodes[a][direction] = b;
            nodes[b][OPPOSITE[direction]] = a;
        }
    }

    return nodes;
}

function crosses(a, b, c, d) {
    const key = p => p.join();
    if (key(a) === key(c) || key(a) === key(d) || key(b) === key(c) || key(b) === key(d))
        return false;
    const side = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
    const s1 = side(a, b, c), s2 = side(a, b, d), s3 = side(c, d, a), s4 = side(c, d, b);
    return s1 !== 0 && s2 !== 0 && s3 !== 0 && s4 !== 0 && s1 !== s2 && s3 !== s4;
}

function overNode(a, b, cells) {
    const steps = Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) * 8;
    for (let i = 1; i < steps; i++) {
        const t = i / steps;
        const x = a[0] + (b[0] - a[0]) * t;
        const y = a[1] + (b[1] - a[1]) * t;
        if (cells.some(p => p !== a && p !== b && Math.abs(p[0] - x) < 0.45 && Math.abs(p[1] - y) < 0.45))
            return true;
    }
    return false;
}

function measure(nodes, positions) {
    const cells = Object.values(positions);
    const segments = [];
    const totals = { wrongSide: 0, crossings: 0, overNode: 0, overlaps: 0 };

    for (const a of Object.keys(nodes)) {
        for (const [direction, b] of Object.entries(nodes[a])) {
            const [pa, pb] = [positions[a], positions[b]];
            const [dx, dy] = VECTOR[direction];
            if ((pb[0] - pa[0]) * dx + (pb[1] - pa[1]) * dy <= 0)
                totals.wrongSide++;
            if (Number(a) < b) {
                segments.push([pa, pb]);
                if (overNode(pa, pb, cells))
                    totals.overNode++;
            }
        }
    }

    for (let i = 0; i < segments.length; i++) {
        for (let j = i + 1; j < segments.length; j++) {
            if (crosses(...segments[i], ...segments[j]))
                totals.crossings++;
        }
    }

    totals.overlaps = cells.length - new Set(cells.map(p => p.join())).size;
    return totals;
}

test("calidad en 300 grafos generados (6-25 workspaces, con ciclos)", () => {
    const totals = { wrongSide: 0, crossings: 0, overNode: 0, overlaps: 0 };

    for (let seed = 1; seed <= 300; seed++) {
        const nodes = generate(6 + (seed % 20), seed, seed % 4);
        const positions = Layout.layoutGraph(nodes, 1, 16 / 9, 9 / 16, 0.3, 0.5);
        const result = measure(nodes, positions);
        for (const key in totals)
            totals[key] += result[key];
    }

    // Measured when this layout was introduced: 164 / 121 / 344 / 0 (the
    // previous first-free-cell layout gave 756 / 255 / 419 / 0). Limits
    // leave a little room for tuning without hiding a regression.
    assert.equal(totals.overlaps, 0, "workspaces solapados");
    assert.ok(totals.wrongSide <= 180, `relaciones en el lado incorrecto: ${totals.wrongSide}`);
    assert.ok(totals.crossings <= 140, `cruces de líneas: ${totals.crossings}`);
    assert.ok(totals.overNode <= 380, `líneas sobre otro workspace: ${totals.overNode}`);
});
