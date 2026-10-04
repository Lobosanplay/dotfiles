#!/usr/bin/env python3
"""Workspace graph viewer: a GTK4 layer-shell overlay for Hyprland.

Usage:
    workspace-viewer.py '<state-json>'

The state is produced by hypr/modules/workspace_viewer.lua:
    {"active": 4, "monitor": "eDP-1",
     "workspaces": {"3": {"left": 2, "right": 4}, ...}}
"""

import ctypes.util
import json
import os
import subprocess
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

# Geometry, in logical pixels at scale 1.0. The whole graph is scaled
# uniformly to fit the surface, so these only set proportions.
NODE_W = 120
NODE_H = 80
PITCH_X = 200  # distance between neighbouring node centres
PITCH_Y = 150
RADIUS = 14
COMPONENT_GAP = 1  # empty grid cells between disconnected components

MARGIN = 48  # space kept free around the graph
FOOTER_H = 40
MAX_SCALE = 1.5  # keep small graphs from becoming huge

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

    return nodes, data.get("active"), data.get("monitor")


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

    return positions


def normalised(component):
    """Shift a component so its top-left cell is (0, 0)."""
    min_x = min(x for x, _ in component.values())
    min_y = min(y for _, y in component.values())

    return {
        node: (x - min_x, y - min_y)
        for node, (x, y) in component.items()
    }


def layout_graph(nodes, center):
    """Return {workspace: (x, y)} in grid units with `center` at (0, 0).

    The component containing `center` is expanded around it by BFS.
    Disconnected components are placed alternately to the right and to
    the left of it, vertically centred, ordered by their lowest id.
    """
    if not nodes:
        return {}

    if center not in nodes:
        center = min(nodes)

    visited = set()
    positions = layout_component(nodes, center, visited)

    right_edge = max(x for x, _ in positions.values())
    left_edge = min(x for x, _ in positions.values())

    others = [
        normalised(layout_component(nodes, root, visited))
        for root in sorted(nodes)
        if root not in visited
    ]

    for index, comp in enumerate(others):
        comp_w = max(x for x, _ in comp.values()) + 1
        comp_h = max(y for _, y in comp.values()) + 1
        offset_y = -(comp_h - 1) / 2

        if index % 2 == 0:
            offset_x = right_edge + 1 + COMPONENT_GAP
            right_edge = offset_x + comp_w - 1
        else:
            offset_x = left_edge - COMPONENT_GAP - comp_w
            left_edge = offset_x

        for node, (x, y) in comp.items():
            positions[node] = (x + offset_x, y + offset_y)

    return positions


def fit_transform(positions, width, height):
    """Uniform scale that fits the graph with (0, 0) at the centre.

    Returns (scale, origin_x, origin_y): a grid point (x, y) is drawn at
    origin + (x * PITCH_X, y * PITCH_Y) * scale.
    """
    reach_x = max((abs(x) for x, _ in positions.values()), default=0)
    reach_y = max((abs(y) for _, y in positions.values()), default=0)

    needed_w = 2 * reach_x * PITCH_X + NODE_W
    needed_h = 2 * reach_y * PITCH_Y + NODE_H

    # The footer is reserved at both ends so the centre stays centred.
    available_w = max(width - 2 * MARGIN, 1)
    available_h = max(height - 2 * (MARGIN + FOOTER_H), 1)

    scale = min(available_w / needed_w, available_h / needed_h, MAX_SCALE)

    return scale, width / 2, height / 2


# ----------------------------------------------------------------------
# NAVIGATION
# ----------------------------------------------------------------------


def neighbor(nodes, positions, current, direction):
    """Workspace reached from `current` by moving in `direction`.

    Graph connections win. Without one, fall back to the nearest node
    that lies in that direction on screen, so isolated workspaces and
    other components remain reachable.
    """
    target = nodes.get(current, {}).get(direction)
    if target in positions:
        return target

    dx, dy = DIRECTIONS[direction]
    cx, cy = positions[current]
    best, best_score = None, None

    for node, (x, y) in positions.items():
        primary = (x - cx) * dx + (y - cy) * dy
        secondary = abs((x - cx) * dy) + abs((y - cy) * dx)

        # Only consider nodes within a 45 degree cone of the direction.
        if node == current or primary <= 0 or secondary > primary:
            continue

        score = (primary + 2 * secondary, node)

        if best_score is None or score < best_score:
            best, best_score = node, score

    return best


# ----------------------------------------------------------------------
# VIEW
# ----------------------------------------------------------------------


class GraphView(Gtk.DrawingArea):
    def __init__(self, nodes, active):
        super().__init__()

        self.nodes = nodes
        self.active = active
        self.edges = edges_of(nodes)
        self.positions = layout_graph(nodes, active)

        self.selected = active if active in self.positions else None

        # Cached fit, recomputed only when the surface size changes.
        self._fit_size = None
        self._fit = None

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self.on_draw)

    def move_selection(self, direction):
        if not self.positions:
            return

        if self.selected is None:
            self.selected = min(self.positions)
        else:
            target = neighbor(self.nodes, self.positions, self.selected, direction)
            if target is None:
                return
            self.selected = target

        self.queue_draw()

    # -- geometry -------------------------------------------------------

    def fit(self, width, height):
        if self._fit_size != (width, height):
            self._fit_size = (width, height)
            self._fit = fit_transform(self.positions, width, height)
        return self._fit

    def node_rect(self, node, fit):
        scale, origin_x, origin_y = fit
        x, y = self.positions[node]
        w, h = NODE_W * scale, NODE_H * scale

        cx = origin_x + x * PITCH_X * scale
        cy = origin_y + y * PITCH_Y * scale

        return cx - w / 2, cy - h / 2, w, h

    def node_center(self, node, fit):
        x, y, w, h = self.node_rect(node, fit)
        return x + w / 2, y + h / 2

    # -- drawing helpers ------------------------------------------------

    @staticmethod
    def rounded_rect(cr, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()

    def draw_text(self, cr, text, cx, cy, size_px, bold=False):
        layout = self.create_pango_layout(text)
        font = Pango.FontDescription.from_string(f"Sans {'Bold' if bold else ''}")
        font.set_absolute_size(max(size_px, 6) * Pango.SCALE)
        layout.set_font_description(font)

        _, logical = layout.get_pixel_extents()
        cr.move_to(cx - logical.width / 2, cy - logical.height / 2)
        PangoCairo.show_layout(cr, layout)
        return logical.width, logical.height

    def palette(self):
        """Theme foreground plus a contrasting colour derived from it.

        The surface itself is transparent, so every node carries its own
        fill in the contrast colour to stay readable over any wallpaper.
        """
        fg = self.get_color()
        luminance = 0.2126 * fg.red + 0.7152 * fg.green + 0.0722 * fg.blue
        contrast = (0.08, 0.08, 0.10) if luminance > 0.5 else (0.96, 0.96, 0.96)
        return (fg.red, fg.green, fg.blue), contrast

    # -- main draw ------------------------------------------------------

    def on_draw(self, _area, cr, width, height):
        if not self.positions:
            return

        fit = self.fit(width, height)
        scale = fit[0]
        fg, bg = self.palette()

        def source(colour, alpha):
            cr.set_source_rgba(*colour, alpha)

        radius = RADIUS * scale
        line = max(2 * scale, 1.5)

        # Edges, clipped so they stop at the node borders. A wider line in
        # the contrast colour underneath keeps them visible on any wallpaper.
        cr.save()
        cr.rectangle(0, 0, width, height)
        for node in self.positions:
            self.rounded_rect(cr, *self.node_rect(node, fit), radius)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()

        for colour, alpha, extra in ((bg, 0.6, 3), (fg, 0.85, 0)):
            source(colour, alpha)
            cr.set_line_width(line + extra)
            for a, b in self.edges:
                cr.move_to(*self.node_center(a, fit))
                cr.line_to(*self.node_center(b, fit))
                cr.stroke()
        cr.restore()

        # Nodes
        label_px = NODE_H * scale * 0.38

        for node in sorted(self.positions):
            x, y, w, h = self.node_rect(node, fit)
            is_active = node == self.active

            self.rounded_rect(cr, x, y, w, h, radius)

            if is_active:
                source(fg, 0.95)
                cr.fill()
                source(bg, 1.0)
            else:
                source(bg, 0.85)
                cr.fill_preserve()
                source(fg, 0.6)
                cr.set_line_width(line * 0.75)
                cr.stroke()
                source(fg, 1.0)

            self.draw_text(cr, str(node), x + w / 2, y + h / 2, label_px, bold=is_active)

            if node == self.selected:
                ring = max(6 * scale, 4)
                ring_rect = (x - ring, y - ring, w + 2 * ring, h + 2 * ring)

                for colour, alpha, width_ in ((bg, 0.7, line * 2.5), (fg, 1.0, line * 1.5)):
                    self.rounded_rect(cr, *ring_rect, radius + ring)
                    source(colour, alpha)
                    cr.set_line_width(width_)
                    cr.stroke()

        self.draw_footer(cr, width, height, fg, bg)

    def draw_footer(self, cr, width, height, fg, bg):
        active_label = "—" if self.active is None else str(self.active)
        footer = f"Active: {active_label}"
        if self.selected is not None and self.selected != self.active:
            footer += f"    Selected: {self.selected}"

        layout = self.create_pango_layout(footer)
        _, logical = layout.get_pixel_extents()

        pill_w = logical.width + 32
        pill_h = FOOTER_H * 0.75
        cx = width / 2
        cy = height - MARGIN - FOOTER_H / 2

        self.rounded_rect(cr, cx - pill_w / 2, cy - pill_h / 2, pill_w, pill_h, pill_h / 2)
        cr.set_source_rgba(*bg, 0.85)
        cr.fill()

        cr.set_source_rgba(*fg, 1.0)
        cr.move_to(cx - logical.width / 2, cy - logical.height / 2)
        PangoCairo.show_layout(cr, layout)


# ----------------------------------------------------------------------
# APPLICATION
# ----------------------------------------------------------------------


class ViewerApp(Gtk.Application):
    def __init__(self, nodes, active, monitor):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.nodes = nodes
        self.active = active
        self.monitor = monitor

    def do_activate(self):
        window = Gtk.Window(application=self, title="Workspace Graph")
        window.add_css_class("workspace-viewer")

        css = Gtk.CssProvider()
        css.load_from_string(
            "window.workspace-viewer { background-color: transparent; }"
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

        # Fullscreen: anchored to every edge of the output. An exclusive
        # zone of -1 also covers areas reserved by bars, and the layout
        # of tiled windows is never touched.
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(window, edge, True)
        Gtk4LayerShell.set_exclusive_zone(window, -1)

        output = find_monitor(self.monitor)
        if output is not None:
            Gtk4LayerShell.set_monitor(window, output)

        self.view = GraphView(self.nodes, self.active)
        window.set_child(self.view)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key_pressed)
        window.add_controller(keys)

        window.present()

    def activate_selected(self):
        selected = self.view.selected

        if selected is not None and selected != self.active:
            # Hand the activation back to Hyprland's Lua side, which owns
            # the workspace graph.
            subprocess.run(
                [
                    "hyprctl",
                    "dispatch",
                    f"function() WorkspaceViewer.activate({int(selected)}) end",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        self.quit()

    def on_key_pressed(self, _controller, keyval, _keycode, _state):
        move = self.view.move_selection
        actions = {
            Gdk.KEY_Escape: self.quit,
            Gdk.KEY_Return: self.activate_selected,
            Gdk.KEY_KP_Enter: self.activate_selected,
            Gdk.KEY_Left: lambda: move("left"),
            Gdk.KEY_Right: lambda: move("right"),
            Gdk.KEY_Up: lambda: move("up"),
            Gdk.KEY_Down: lambda: move("down"),
        }

        action = actions.get(keyval)
        if action is None:
            return False

        action()
        return True


def find_monitor(connector):
    """GDK monitor for a Hyprland monitor name such as eDP-1."""
    if not connector:
        return None

    monitors = Gdk.Display.get_default().get_monitors()

    for index in range(monitors.get_n_items()):
        monitor = monitors.get_item(index)
        if monitor.get_connector() == connector:
            return monitor

    return None


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    if not Gtk4LayerShell.is_supported():
        print("workspace-viewer: layer-shell not supported", file=sys.stderr)
        return 1

    nodes, active, monitor = parse_state(sys.argv[1])
    app = ViewerApp(nodes, active, monitor)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
