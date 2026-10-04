#!/usr/bin/env python3
"""Workspace graph viewer: a GTK4 layer-shell overlay for Hyprland.

Usage:
    workspace-viewer.py '<state-json>'

The state is produced by hypr/modules/workspace_viewer.lua:
    {"active": 4, "workspaces": {"3": {"left": 2, "right": 4}, ...}}
"""

import ctypes.util
import json
import os
import sys
from collections import deque

# gtk4-layer-shell must be loaded before libwayland-client, which only
# works through LD_PRELOAD when used from Python.
LAYER_SHELL_LIB = "libgtk4-layer-shell.so"

if LAYER_SHELL_LIB not in os.environ.get("LD_PRELOAD", ""):
    lib = ctypes.util.find_library("gtk4-layer-shell") or LAYER_SHELL_LIB + ".0"
    preload = " ".join(filter(None, [lib, os.environ.get("LD_PRELOAD")]))
    os.execve(
        sys.executable,
        [sys.executable] + sys.argv,
        {**os.environ, "LD_PRELOAD": preload},
    )

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gdk, Gio, Gtk, Gtk4LayerShell, Pango, PangoCairo

APP_ID = "dev.lobosanplay.WorkspaceViewer"
NAMESPACE = "workspace-viewer"

DIRECTIONS = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
}

# Geometry (pixels)
NODE_W = 64
NODE_H = 44
GAP_X = 56
GAP_Y = 40
COMPONENT_GAP = 1  # empty grid rows between disconnected components
PADDING = 36
HEADER_H = 48
FOOTER_H = 40
RADIUS = 10

# ----------------------------------------------------------------------
# MODEL
# ----------------------------------------------------------------------


def parse_state(raw):
    data = json.loads(raw)
    nodes = {}

    for key, connections in data.get("workspaces", {}).items():
        nodes[int(key)] = {
            direction: int(target)
            for direction, target in connections.items()
            if direction in DIRECTIONS
        }

    # Make sure every edge target exists as a node.
    for connections in list(nodes.values()):
        for target in connections.values():
            nodes.setdefault(target, {})

    active = data.get("active")
    return nodes, active


def edges_of(nodes):
    """Undirected edges, deduplicated."""
    edges = set()

    for source, connections in nodes.items():
        for target in connections.values():
            if target != source:
                edges.add((min(source, target), max(source, target)))

    return sorted(edges)


# ----------------------------------------------------------------------
# LAYOUT
# ----------------------------------------------------------------------


def nearest_free_cell(cell, taken):
    x, y = cell
    radius = 1

    while True:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                candidate = (x + dx, y + dy)
                if candidate not in taken:
                    return candidate
        radius += 1


def layout_component(nodes, root, visited):
    """Place one connected component on a grid using BFS over directions.

    Cycles or inconsistent connections that would put two workspaces in
    the same cell are resolved by moving the newcomer to the nearest free
    cell; its edges are still drawn, just not axis-aligned.
    """
    positions = {root: (0, 0)}
    taken = {(0, 0): root}
    queue = deque([root])
    visited.add(root)

    while queue:
        current = queue.popleft()
        cx, cy = positions[current]

        for direction, target in sorted(nodes[current].items()):
            if target in visited:
                continue

            dx, dy = DIRECTIONS[direction]
            cell = (cx + dx, cy + dy)

            if cell in taken:
                cell = nearest_free_cell(cell, taken)

            positions[target] = cell
            taken[cell] = target
            visited.add(target)
            queue.append(target)

        # Also follow edges declared only on the other side.
        for other, connections in sorted(nodes.items()):
            if other in visited or current not in connections.values():
                continue

            direction = next(d for d, t in connections.items() if t == current)
            dx, dy = DIRECTIONS[direction]
            cell = (cx - dx, cy - dy)

            if cell in taken:
                cell = nearest_free_cell(cell, taken)

            positions[other] = cell
            taken[cell] = other
            visited.add(other)
            queue.append(other)

    # Normalise to start at (0, 0).
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())

    return {
        node: (x - min_x, y - min_y)
        for node, (x, y) in positions.items()
    }


def layout_graph(nodes):
    """Return {workspace: (col, row)} for every node.

    Components are stacked vertically, ordered by their lowest workspace
    id, and centred horizontally.
    """
    visited = set()
    components = []

    for root in sorted(nodes):
        if root not in visited:
            components.append(layout_component(nodes, root, visited))

    width = max(
        (max(x for x, _ in comp.values()) + 1 for comp in components),
        default=1,
    )

    positions = {}
    row = 0

    for comp in components:
        comp_w = max(x for x, _ in comp.values()) + 1
        comp_h = max(y for _, y in comp.values()) + 1
        offset_x = (width - comp_w) / 2

        for node, (x, y) in comp.items():
            positions[node] = (x + offset_x, y + row)

        row += comp_h + COMPONENT_GAP

    return positions


# ----------------------------------------------------------------------
# VIEW
# ----------------------------------------------------------------------


class GraphView(Gtk.DrawingArea):
    def __init__(self, nodes, active):
        super().__init__()

        self.nodes = nodes
        self.active = active
        self.edges = edges_of(nodes)
        self.positions = layout_graph(nodes)

        # Reserved for keyboard navigation (arrows + Enter) later on.
        self.selected = active

        cols = max((x for x, _ in self.positions.values()), default=0) + 1
        rows = max((y for _, y in self.positions.values()), default=0) + 1

        graph_w = cols * NODE_W + (cols - 1) * GAP_X
        graph_h = rows * NODE_H + (rows - 1) * GAP_Y

        self.graph_w = graph_w
        self.graph_h = graph_h

        self.set_content_width(max(graph_w, 220) + 2 * PADDING)
        self.set_content_height(graph_h + HEADER_H + FOOTER_H + 2 * PADDING)
        self.set_draw_func(self.on_draw)

    def node_rect(self, node, width):
        col, row = self.positions[node]
        origin_x = (width - self.graph_w) / 2
        origin_y = PADDING + HEADER_H

        x = origin_x + col * (NODE_W + GAP_X)
        y = origin_y + row * (NODE_H + GAP_Y)

        return x, y, NODE_W, NODE_H

    def node_center(self, node, width):
        x, y, w, h = self.node_rect(node, width)
        return x + w / 2, y + h / 2

    # -- drawing helpers ------------------------------------------------

    @staticmethod
    def rounded_rect(cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()

    def draw_text(self, cr, text, cx, cy, size_pt, bold=False):
        layout = self.create_pango_layout(text)
        font = Pango.FontDescription.from_string(
            f"Sans {'Bold ' if bold else ''}{size_pt}"
        )
        layout.set_font_description(font)

        _, logical = layout.get_pixel_extents()
        cr.move_to(cx - logical.width / 2, cy - logical.height / 2)
        PangoCairo.show_layout(cr, layout)

    # -- main draw ------------------------------------------------------

    def on_draw(self, _area, cr, width, height):
        # Foreground colour from the GTK theme; everything derives from it.
        fg = self.get_color()

        def source(alpha):
            cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha * alpha)

        source(1.0)
        self.draw_text(cr, "WORKSPACE GRAPH", width / 2, PADDING + 12, 12, bold=True)

        # Edges, clipped so they stop at the node borders.
        cr.save()
        cr.rectangle(0, 0, width, height)
        for node in self.positions:
            self.rounded_rect(cr, *self.node_rect(node, width), RADIUS)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()

        cr.set_line_width(2)
        source(0.45)
        for a, b in self.edges:
            cr.move_to(*self.node_center(a, width))
            cr.line_to(*self.node_center(b, width))
            cr.stroke()
        cr.restore()

        # Nodes
        for node in sorted(self.positions):
            x, y, w, h = self.node_rect(node, width)
            is_active = node == self.active

            self.rounded_rect(cr, x, y, w, h, RADIUS)

            if is_active:
                source(1.0)
                cr.fill()
                # Knock the label out so the window background shows through.
                cr.save()
                cr.set_operator(cairo.OPERATOR_CLEAR)
                self.draw_text(cr, str(node), x + w / 2, y + h / 2, 13, bold=True)
                cr.restore()
            else:
                source(0.08)
                cr.fill_preserve()
                source(0.5)
                cr.set_line_width(1.5)
                cr.stroke()
                source(1.0)
                self.draw_text(cr, str(node), x + w / 2, y + h / 2, 13)

        source(0.7)
        active_label = "—" if self.active is None else str(self.active)
        self.draw_text(
            cr,
            f"Active: {active_label}",
            width / 2,
            height - PADDING - FOOTER_H / 2 + 8,
            10,
        )


# ----------------------------------------------------------------------
# APPLICATION
# ----------------------------------------------------------------------


class ViewerApp(Gtk.Application):
    def __init__(self, nodes, active):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.nodes = nodes
        self.active = active

    def do_activate(self):
        window = Gtk.Window(application=self, title="Workspace Graph")
        window.add_css_class("workspace-viewer")

        css = Gtk.CssProvider()
        css.load_from_string(
            ".workspace-viewer { border-radius: 14px; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        Gtk4LayerShell.init_for_window(window)
        Gtk4LayerShell.set_namespace(window, NAMESPACE)
        Gtk4LayerShell.set_layer(window, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_keyboard_mode(
            window, Gtk4LayerShell.KeyboardMode.EXCLUSIVE
        )
        # No anchors: the compositor centres the surface on the output,
        # and no exclusive zone means the tiling layout is untouched.

        window.set_child(GraphView(self.nodes, self.active))

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        window.add_controller(keys)

        window.present()

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        actions = {
            Gdk.KEY_Escape: self.quit,
        }

        action = actions.get(keyval)
        if action is None:
            return False

        action()
        return True


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    if not Gtk4LayerShell.is_supported():
        print("workspace-viewer: layer-shell not supported", file=sys.stderr)
        return 1

    nodes, active = parse_state(sys.argv[1])
    app = ViewerApp(nodes, active)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
