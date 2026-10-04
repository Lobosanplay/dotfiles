// Unit tests for GraphLayout.js: node --test tests/layout

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { loadLayout, graph, reordered, VECTOR } = require("./load-layout.js");

const Layout = loadLayout();

const GAP_RATIO = 0.3; // as in OverviewWidget.qml
const COMPONENT_GAP = 0.5;
const MAX_SCALE = 0.3;

const VIEWPORTS = [[1920, 1080], [2560, 1440], [3840, 2160], [1600, 900]];

const range = n => Array.from({ length: n }, (_, i) => i + 1);

const CASES = {
    "1: un workspace": graph([1], []),
    "2: 1 - 2": graph([1, 2], [[1, "right", 2]]),
    "3: vertical 1 | 2 | 3": graph([1, 2, 3], [[1, "down", 2], [2, "down", 3]]),
    "4: cruz alrededor de 3": graph([1, 2, 3, 4, 5], [[3, "up", 2], [3, "left", 1], [3, "right", 4], [3, "down", 5]]),
    "5: componentes 1-2 y 3-4": graph([1, 2, 3, 4], [[1, "right", 2], [3, "right", 4]]),
    "6: cadena de 50": graph(range(50), range(49).map(i => [i, "right", i + 1])),
    "ciclo 1-2-3-4": graph([1, 2, 3, 4], [[1, "right", 2], [2, "down", 3], [3, "left", 4], [4, "up", 1]]),
    "colisión (regresión)": graph([2, 3, 8, 9, 10, 11], [[2, "right", 3], [3, "down", 8], [8, "left", 9], [9, "up", 10], [10, "up", 11]]),
};

// Cases with no two paths competing for a cell: every neighbor must be
// exactly one cell away, on the side of its connection.
const COLLISION_FREE = ["2: 1 - 2", "3: vertical 1 | 2 | 3", "4: cruz alrededor de 3", "5: componentes 1-2 y 3-4", "6: cadena de 50"];

function layout(nodes, center, viewport) {
    const [width, height] = viewport;
    return Layout.layoutGraph(nodes, center, width / height, height / width, GAP_RATIO, COMPONENT_GAP);
}

function components(nodes) {
    const seen = new Set();
    const result = [];
    for (const start of Object.keys(nodes).map(Number)) {
        if (seen.has(start))
            continue;
        const component = [];
        const queue = [start];
        seen.add(start);
        while (queue.length > 0) {
            const id = queue.shift();
            component.push(id);
            for (const target of Object.values(nodes[id])) {
                if (!seen.has(target)) {
                    seen.add(target);
                    queue.push(target);
                }
            }
        }
        result.push(component);
    }
    return result;
}

for (const [name, nodes] of Object.entries(CASES)) {
    const ids = Object.keys(nodes).map(Number);

    for (const viewport of VIEWPORTS) {
        for (const center of ids) {
            const label = `${name} | centro ${center} | ${viewport.join("x")}`;
            const positions = layout(nodes, center, viewport);

            test(`${label}: todos los nodos tienen una posición finita, única y razonable`, () => {
                assert.deepEqual(Object.keys(positions).map(Number).sort((a, b) => a - b), ids.slice().sort((a, b) => a - b));
                const cells = new Set();
                for (const [x, y] of Object.values(positions)) {
                    assert.ok(Number.isFinite(x) && Number.isFinite(y), "posición no finita");
                    assert.ok(Math.abs(x) <= 2 * ids.length && Math.abs(y) <= 2 * ids.length, `posición fuera de límites: ${x},${y}`);
                    cells.add(`${x},${y}`);
                }
                assert.equal(cells.size, ids.length, "dos workspaces en la misma posición");
            });

            test(`${label}: el activo es la referencia (0, 0)`, () => {
                assert.deepEqual(positions[center], [0, 0]);
            });

            test(`${label}: determinista, también con otro orden del JSON`, () => {
                assert.deepEqual(layout(nodes, center, viewport), positions);
                assert.deepEqual(layout(reordered(nodes), center, viewport), positions);
            });

            test(`${label}: los vecinos quedan cerca y en el lado de su conexión`, () => {
                for (const a of ids) {
                    for (const [direction, b] of Object.entries(nodes[a])) {
                        const [dx, dy] = VECTOR[direction];
                        const along = (positions[b][0] - positions[a][0]) * dx + (positions[b][1] - positions[a][1]) * dy;
                        const distance = Math.hypot(positions[b][0] - positions[a][0], positions[b][1] - positions[a][1]);
                        assert.ok(along > 0, `${a}.${direction} = ${b} queda en el lado contrario`);
                        assert.ok(distance <= 3, `${a}-${b} demasiado lejos (${distance})`);
                        if (COLLISION_FREE.includes(name))
                            assert.equal(distance, 1, `${a}-${b} debería ser adyacente`);
                    }
                }
            });

            test(`${label}: los componentes desconectados no se solapan`, () => {
                const boxes = components(nodes).map(component => {
                    const xs = component.map(id => positions[id][0]);
                    const ys = component.map(id => positions[id][1]);
                    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
                });
                for (let i = 0; i < boxes.length; i++) {
                    for (let j = i + 1; j < boxes.length; j++) {
                        const [a, b] = [boxes[i], boxes[j]];
                        const overlap = a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];
                        assert.ok(!overlap, `componentes ${i} y ${j} se solapan`);
                    }
                }
            });

            test(`${label}: con la escala calculada, el grafo cabe en la pantalla`, () => {
                const [width, height] = viewport;
                const scale = Layout.fitScale(positions, width, height, width, height, GAP_RATIO, MAX_SCALE);
                assert.ok(scale > 0 && scale <= MAX_SCALE, `escala ${scale}`);
                const points = Object.values(positions);
                const spanX = Math.max(...points.map(p => p[0])) - Math.min(...points.map(p => p[0]));
                const spanY = Math.max(...points.map(p => p[1])) - Math.min(...points.map(p => p[1]));
                const drawnW = (spanX * (1 + GAP_RATIO) + 1) * width * scale;
                const drawnH = (spanY * (1 + GAP_RATIO) + 1) * height * scale;
                assert.ok(drawnW <= width + 1e-6 && drawnH <= height + 1e-6, `${drawnW}x${drawnH} no cabe en ${width}x${height}`);
            });
        }
    }
}

test("un centro que no está en el grafo usa el menor id", () => {
    const positions = layout(CASES["2: 1 - 2"], 99, VIEWPORTS[0]);
    assert.deepEqual(positions[1], [0, 0]);
});

test("grafo vacío: sin posiciones y sin escala", () => {
    assert.deepEqual(Object.keys(layout({}, 1, VIEWPORTS[0])), []);
    assert.equal(Layout.fitScale({}, 1920, 1080, 1920, 1080, GAP_RATIO, MAX_SCALE), null);
});
