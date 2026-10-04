#!/usr/bin/env python3
"""Workspace graph viewer: a GTK4 layer-shell overlay for Hyprland.

Usage:
    workspace-viewer.py '<state-json>'

The state is produced by hypr/modules/workspace_viewer.lua:
    {"active": 4, "monitor": "eDP-1",
     "workspaces": {"3": {"left": 2, "right": 4}, ...},
     "monitors": {"eDP-1": [x, y, logical_w, logical_h], ...},
     "workspace_monitors": {"3": "eDP-1", ...},
     "clients": [{"workspace": 3, "at": [x, y], "size": [w, h],
                  "class": "kitty", "title": "~", "floating": false,
                  "fullscreen": false, "focus": 0}, ...]}

Window positions are global logical coordinates; previews subtract the
origin of the workspace's monitor.
"""

import ctypes.util
import json
import os
import subprocess
import sys
from collections import deque, namedtuple

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
NODE_W = 360
NODE_H = 220
PITCH_X = 440  # distance between neighbouring preview centres
PITCH_Y = 300
RADIUS = 16
COMPONENT_GAP = 0.5  # extra grid cells between disconnected components

PREVIEW_PAD = 14  # space between a preview's border and its mini screen
INFO_SIZE = 22  # diameter of the [i] badge
LABEL_PX = 15  # application name inside a window
TITLE_PX = 12  # window title below it

MARGIN = 48  # space kept free around the graph
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

    active = data.get("active")
    monitor = data.get("monitor")
    frames, windows = parse_previews(data, monitor)

    return nodes, active, monitor, frames, windows


Window = namedtuple("Window", "x y w h app title floating focus")


def app_label(window_class, title):
    """Short application name: "brave-browser" -> "Brave"."""
    name = (window_class or title or "?").split(".")[-1].split("-")[0]
    return name[:1].upper() + name[1:]


def parse_previews(data, viewer_monitor):
    """Monitor frame and windows of each workspace, in monitor coordinates.

    Returns (frames, windows): frames maps workspace -> (width, height) of
    the monitor showing it, plus a None key used for unknown workspaces;
    windows maps workspace -> [Window], ordered back to front.
    """
    monitors = {
        name: tuple(frame) for name, frame in data.get("monitors", {}).items()
    }
    default = monitors.get(viewer_monitor) or next(
        iter(monitors.values()), (0, 0, 16, 10)
    )

    workspace_monitor = {
        int(key): monitors.get(name, default)
        for key, name in data.get("workspace_monitors", {}).items()
    }

    frames = {None: default[2:]}
    frames.update({ws: frame[2:] for ws, frame in workspace_monitor.items()})

    windows = {}

    for client in data.get("clients", []):
        workspace = int(client["workspace"])
        origin_x, origin_y, frame_w, frame_h = workspace_monitor.get(workspace, default)

        if client.get("fullscreen"):
            x0, y0, x1, y1 = 0, 0, frame_w, frame_h
        else:
            x = client["at"][0] - origin_x
            y = client["at"][1] - origin_y
            # Clamp into the monitor so nothing lands outside the preview.
            x0 = min(max(x, 0), frame_w)
            y0 = min(max(y, 0), frame_h)
            x1 = min(max(x + client["size"][0], 0), frame_w)
            y1 = min(max(y + client["size"][1], 0), frame_h)

        if x1 - x0 < 1 or y1 - y0 < 1:
            continue

        windows.setdefault(workspace, []).append(Window(
            x0, y0, x1 - x0, y1 - y0,
            app_label(client.get("class"), client.get("title")),
            client.get("title") or "",
            bool(client.get("floating")),
            int(client.get("focus", 0)),
        ))

    # Tiled below floating; within each, least recently focused first.
    for items in windows.values():
        items.sort(key=lambda win: (win.floating, -win.focus))

    return frames, windows


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


def layout_graph(nodes, center, aspect=16 / 10):
    """Return {workspace: (x, y)} in grid units with `center` at (0, 0).

    The component containing `center` is expanded around it by BFS.
    Each disconnected component, ordered by its lowest id, goes to the
    side (right, left, below, above) that keeps the largest scale for a
    viewport of the given aspect ratio.
    """
    if not nodes:
        return {}

    if center not in nodes:
        center = min(nodes)

    visited = set()
    positions = layout_component(nodes, center, visited)

    others = [
        normalised(layout_component(nodes, root, visited))
        for root in sorted(nodes)
        if root not in visited
    ]

    def relative_scale(xs, ys):
        needed_w = (max(xs) - min(xs)) * PITCH_X + NODE_W
        needed_h = (max(ys) - min(ys)) * PITCH_Y + NODE_H
        return min(aspect / needed_w, 1 / needed_h)

    for comp in others:
        comp_w = max(x for x, _ in comp.values()) + 1
        comp_h = max(y for _, y in comp.values()) + 1

        xs = [x for x, _ in positions.values()]
        ys = [y for _, y in positions.values()]
        mid_x = -(comp_w - 1) / 2
        mid_y = -(comp_h - 1) / 2

        offsets = (
            (max(xs) + 1 + COMPONENT_GAP, mid_y),  # right
            (min(xs) - COMPONENT_GAP - comp_w, mid_y),  # left
            (mid_x, max(ys) + 1 + COMPONENT_GAP),  # below
            (mid_x, min(ys) - COMPONENT_GAP - comp_h),  # above
        )

        # max() keeps the first offset on ties, so the order above is
        # the deterministic preference.
        offset_x, offset_y = max(
            offsets,
            key=lambda off: relative_scale(
                xs + [off[0], off[0] + comp_w - 1],
                ys + [off[1], off[1] + comp_h - 1],
            ),
        )

        for node, (x, y) in comp.items():
            positions[node] = (x + offset_x, y + offset_y)

    return positions


def fit_transform(positions, width, height):
    """Uniform scale that fits the whole graph inside the surface.

    The scale comes from the graph's bounding box. The centre workspace
    at (0, 0) is then moved as close to the middle of the surface as the
    margins allow.

    Returns (scale, origin_x, origin_y): a grid point (x, y) is drawn at
    origin + (x * PITCH_X, y * PITCH_Y) * scale.
    """
    xs = [x for x, _ in positions.values()] or [0]
    ys = [y for _, y in positions.values()] or [0]

    needed_w = (max(xs) - min(xs)) * PITCH_X + NODE_W
    needed_h = (max(ys) - min(ys)) * PITCH_Y + NODE_H

    available_w = max(width - 2 * MARGIN, 1)
    available_h = max(height - 2 * MARGIN, 1)

    scale = min(available_w / needed_w, available_h / needed_h, MAX_SCALE)

    def centred(size, low, high, pitch, node):
        # Range of origins that keep the graph inside the margins.
        lowest = MARGIN - low * pitch * scale + node * scale / 2
        highest = size - MARGIN - high * pitch * scale - node * scale / 2
        return min(max(size / 2, lowest), max(highest, lowest))

    return (
        scale,
        centred(width, min(xs), max(xs), PITCH_X, NODE_W),
        centred(height, min(ys), max(ys), PITCH_Y, NODE_H),
    )


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
    def __init__(self, nodes, active, frames, windows):
        super().__init__()

        self.nodes = nodes
        self.active = active
        self.frames = frames
        self.windows = windows
        self.edges = edges_of(nodes)
        # The viewer's own monitor frame sets the aspect to lay out for.
        frame_w, frame_h = frames[None]
        self.positions = layout_graph(nodes, active, frame_w / frame_h)

        self.selected = active if active in self.positions else None

        # Workspaces whose [i] badge currently shows their number.
        self.info_shown = set()
        self._badges = {}

        # Cached fit, recomputed only when the surface size changes.
        self._fit_size = None
        self._fit = None

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_draw_func(self.on_draw)

        click = Gtk.GestureClick()
        click.connect("pressed", self.on_click)
        self.add_controller(click)

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

    def toggle_info(self, workspace):
        if workspace is None:
            return

        self.info_shown ^= {workspace}
        self.queue_draw()

    def on_click(self, _gesture, _n_press, x, y):
        for workspace, (bx, by, bw, bh) in self._badges.items():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.toggle_info(workspace)
                return

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

    def screen_rect(self, node, rect, scale):
        """The workspace's monitor, letterboxed inside its preview."""
        x, y, w, h = rect
        pad = PREVIEW_PAD * scale
        frame_w, frame_h = self.frames.get(node, self.frames[None])

        fit = min((w - 2 * pad) / frame_w, (h - 2 * pad) / frame_h)
        sw, sh = frame_w * fit, frame_h * fit

        return x + (w - sw) / 2, y + (h - sh) / 2, sw, sh, fit

    # -- drawing helpers ------------------------------------------------

    @staticmethod
    def rounded_rect(cr, x, y, w, h, r):
        r = max(min(r, w / 2, h / 2), 0)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()

    def text_layout(self, text, size_px, bold=False, max_width=None):
        layout = self.create_pango_layout(text)
        font = Pango.FontDescription.from_string("Sans Bold" if bold else "Sans")
        font.set_absolute_size(size_px * Pango.SCALE)
        layout.set_font_description(font)

        if max_width is not None:
            layout.set_width(int(max(max_width, 1) * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            layout.set_alignment(Pango.Alignment.CENTER)

        return layout

    def palette(self):
        """Theme foreground plus a contrasting colour derived from it.

        The surface itself is transparent, so every preview carries its
        own fill in the contrast colour to stay readable over any wallpaper.
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

        # Edges, clipped so they stop at the preview borders. A wider line
        # in the contrast colour keeps them visible on any wallpaper.
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

        self._badges = {}

        for node in sorted(self.positions):
            rect = self.node_rect(node, fit)
            self.draw_preview(cr, node, rect, scale, fg, bg, source, radius, line)

    def draw_preview(self, cr, node, rect, scale, fg, bg, source, radius, line):
        x, y, w, h = rect
        is_active = node == self.active

        # Card
        self.rounded_rect(cr, x, y, w, h, radius)
        source(bg, 0.82)
        cr.fill_preserve()
        if is_active:
            source(fg, 0.07)
            cr.fill_preserve()
            source(fg, 0.95)
            cr.set_line_width(line * 1.5)
        else:
            source(fg, 0.35)
            cr.set_line_width(line * 0.75)
        cr.stroke()

        # Mini screen with the workspace's windows
        sx, sy, sw, sh, to_preview = self.screen_rect(node, rect, scale)

        cr.save()
        self.rounded_rect(cr, sx, sy, sw, sh, radius * 0.4)
        source(fg, 0.05)
        cr.fill_preserve()
        cr.clip()

        gap = max(1.5 * scale, 1)
        for window in self.windows.get(node, []):
            self.draw_window(
                cr,
                window,
                sx + window.x * to_preview + gap,
                sy + window.y * to_preview + gap,
                window.w * to_preview - 2 * gap,
                window.h * to_preview - 2 * gap,
                scale, fg, bg, source, radius,
            )
        cr.restore()

        self.draw_badge(cr, node, rect, scale, fg, bg, source)

        if node == self.selected:
            ring = max(6 * scale, 4)
            ring_rect = (x - ring, y - ring, w + 2 * ring, h + 2 * ring)

            for colour, alpha, width_ in ((bg, 0.7, line * 2.5), (fg, 1.0, line * 1.5)):
                self.rounded_rect(cr, *ring_rect, radius + ring)
                source(colour, alpha)
                cr.set_line_width(width_)
                cr.stroke()

    def draw_window(self, cr, window, x, y, w, h, scale, fg, bg, source, radius):
        if w < 2 or h < 2:
            return

        self.rounded_rect(cr, x, y, w, h, radius * 0.3)
        source(bg, 0.9)
        cr.fill_preserve()
        source(fg, 0.10)
        cr.fill_preserve()
        source(fg, 0.55)
        cr.set_line_width(max(scale, 1))
        cr.stroke()

        # Labels only where they fit: app name, then the title if room.
        label_px = max(LABEL_PX * scale, 7)
        title_px = max(TITLE_PX * scale, 6)
        text_w = w - 8 * scale

        if text_w < label_px * 2 or h < label_px * 1.6:
            return

        app = self.text_layout(window.app, label_px, bold=True, max_width=text_w)
        _, app_ext = app.get_pixel_extents()

        title = None
        if window.title and window.title.lower() != window.app.lower():
            title = self.text_layout(window.title, title_px, max_width=text_w)
            _, title_ext = title.get_pixel_extents()
            if app_ext.height + title_ext.height + 4 * scale > h * 0.9:
                title = None

        total = app_ext.height + (title_ext.height + 2 * scale if title else 0)
        top = y + (h - total) / 2

        source(fg, 1.0)
        cr.move_to(x + 4 * scale, top)
        PangoCairo.show_layout(cr, app)

        if title:
            source(fg, 0.65)
            cr.move_to(x + 4 * scale, top + app_ext.height + 2 * scale)
            PangoCairo.show_layout(cr, title)

    def draw_badge(self, cr, node, rect, scale, fg, bg, source):
        """Small [i] in the top-right corner; shows the number on demand."""
        x, y, w, _ = rect
        size = max(INFO_SIZE * scale, 14)
        showing = node in self.info_shown

        layout = self.text_layout(str(node) if showing else "i", size * 0.6, bold=True)
        _, ext = layout.get_pixel_extents()

        badge_w = max(size, ext.width + size * 0.6)
        inset = max(PREVIEW_PAD * scale * 0.5, 3)
        bx, by = x + w - inset - badge_w, y + inset

        self.rounded_rect(cr, bx, by, badge_w, size, size / 2)
        source(fg if showing else bg, 0.95)
        cr.fill_preserve()
        source(fg, 0.6)
        cr.set_line_width(1)
        cr.stroke()

        source(bg if showing else fg, 1.0)
        cr.move_to(bx + (badge_w - ext.width) / 2, by + (size - ext.height) / 2)
        PangoCairo.show_layout(cr, layout)

        self._badges[node] = (bx, by, badge_w, size)


# ----------------------------------------------------------------------
# APPLICATION
# ----------------------------------------------------------------------


class ViewerApp(Gtk.Application):
    def __init__(self, nodes, active, monitor, frames, windows):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.nodes = nodes
        self.active = active
        self.monitor = monitor
        self.frames = frames
        self.windows = windows

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

        self.view = GraphView(self.nodes, self.active, self.frames, self.windows)
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
            Gdk.KEY_i: lambda: self.view.toggle_info(self.view.selected),
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

    nodes, active, monitor, frames, windows = parse_state(sys.argv[1])
    app = ViewerApp(nodes, active, monitor, frames, windows)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
