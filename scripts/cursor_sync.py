#!/usr/bin/env python3
"""Make one cursor theme and size apply to every application.

DMS owns the cursor preference (``cursorSettings`` in its settings.json) and
exports it to Hyprland. That is not enough for a uniform cursor: libXcursor
(XWayland, Java/Minecraft, GTK3) and Hyprcursor (compositor-drawn cursors)
each pick the nearest image size the theme ships, without rescaling. A theme
whose Xcursor files contain 24/32 px and whose Hyprcursor files contain 24/36
px is drawn at 32 px in XWayland apps and 36 px in Wayland apps.

This script reads the DMS preference and:

* regenerates a user-installed theme so both formats contain exactly the
  preferred size and its monitor-scale multiples, resampled from a pristine
  snapshot of the original art;
* points the remaining consumers (GSettings, the default Xcursor theme,
  Xresources, Flatpak) at the same theme and size.

``--check`` reports drift without changing anything. ``--apply`` is
idempotent; asset generation only runs when its inputs change.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


sys.dont_write_bytecode = True

HOME = Path.home()
DMS_SETTINGS = HOME / ".config/DankMaterialShell/settings.json"
DMS_CURSOR_LUA = HOME / ".config/hypr/dms/cursor.lua"
XCURSOR_USER_DIRS = (HOME / ".local/share/icons", HOME / ".icons")
SOURCE_ROOT = HOME / ".local/share/dotfiles/cursor-sources"
STAMP = HOME / ".local/state/dotfiles/cursor-sync.json"
DEFAULT_THEME_INDEX = HOME / ".icons/default/index.theme"
XRESOURCES = HOME / ".Xresources"
GENERATED_MARKER = ".dotfiles-cursor-generated"

FALLBACK_THEME = "Adwaita"
FALLBACK_SIZE = 36
# Scales always generated in addition to the live monitor scales, so that a
# new monitor does not require a regeneration before its cursor is crisp.
BASE_SCALES = (1.0, 2.0)
GENERATOR_VERSION = 1

XCURSOR_MAGIC = b"Xcur"
XCURSOR_IMAGE = 0xFFFD0002


# --------------------------------------------------------------------------
# Xcursor format
# --------------------------------------------------------------------------

@dataclass
class Frame:
    nominal: int
    width: int
    height: int
    xhot: int
    yhot: int
    delay: int
    pixels: bytes  # little-endian premultiplied ARGB32 (B, G, R, A in memory)


def read_xcursor(data: bytes) -> list[Frame]:
    if data[:4] != XCURSOR_MAGIC:
        raise ValueError("not an Xcursor file")
    header, _version, ntoc = struct.unpack_from("<III", data, 4)
    frames = []
    for index in range(ntoc):
        kind, _subtype, position = struct.unpack_from("<III", data, header + 12 * index)
        if kind != XCURSOR_IMAGE:
            continue
        (_size, _kind, nominal, _ver, width, height, xhot, yhot, delay) = struct.unpack_from(
            "<IIIIIIIII", data, position
        )
        start = position + 36
        pixels = data[start:start + 4 * width * height]
        if len(pixels) != 4 * width * height:
            raise ValueError("truncated Xcursor image")
        frames.append(Frame(nominal, width, height, xhot, yhot, delay, pixels))
    if not frames:
        raise ValueError("Xcursor file has no images")
    return frames


def write_xcursor(frames: list[Frame]) -> bytes:
    header = 16
    toc = bytearray()
    chunks = bytearray()
    position = header + 12 * len(frames)
    for frame in frames:
        toc += struct.pack("<III", XCURSOR_IMAGE, frame.nominal, position)
        chunk = struct.pack(
            "<IIIIIIIII", 36, XCURSOR_IMAGE, frame.nominal, 1,
            frame.width, frame.height, frame.xhot, frame.yhot, frame.delay,
        ) + frame.pixels
        chunks += chunk
        position += len(chunk)
    return XCURSOR_MAGIC + struct.pack("<III", header, 0x10000, len(frames)) + bytes(toc) + bytes(chunks)


def largest_frames(frames: list[Frame]) -> list[Frame]:
    """Return the animation at the theme's highest nominal size."""
    nominal = max(frame.nominal for frame in frames)
    return [frame for frame in frames if frame.nominal == nominal]


# --------------------------------------------------------------------------
# Resampling (Pillow is imported lazily so --check works without it)
# --------------------------------------------------------------------------

def _image(frame: Frame):
    from PIL import Image

    straight = Image.frombytes("RGBA", (frame.width, frame.height), frame.pixels, "raw", "BGRA")
    # Xcursor pixels are premultiplied; resampling in premultiplied space
    # avoids dark fringes around transparent edges.
    return Image.frombytes("RGBa", straight.size, straight.tobytes())


def scale_frame(frame: Frame, nominal: int) -> Frame:
    from PIL import Image

    factor = nominal / frame.nominal
    width = max(1, round(frame.width * factor))
    height = max(1, round(frame.height * factor))
    image = _image(frame)
    if (width, height) != image.size:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    pixels = Image.frombytes("RGBA", image.size, image.tobytes()).tobytes("raw", "BGRA")
    return Frame(
        nominal, width, height,
        min(width - 1, round(frame.xhot * factor)),
        min(height - 1, round(frame.yhot * factor)),
        frame.delay, pixels,
    )


def frame_png(frame: Frame) -> bytes:
    buffer = io.BytesIO()
    _image(frame).convert("RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Hyprcursor format
# --------------------------------------------------------------------------

def hyprcursor_archive(source: list[Frame], scaled: dict[int, list[Frame]]) -> bytes:
    reference = source[0]
    lines = [
        "resize_algorithm = bilinear",
        f"hotspot_x = {reference.xhot / reference.width:.8f}",
        f"hotspot_y = {reference.yhot / reference.height:.8f}",
    ]
    files = {}
    for nominal, frames in sorted(scaled.items()):
        for index, frame in enumerate(frames):
            name = f"image-{nominal}-{index:02d}.png"
            files[name] = frame_png(frame)
            if len(frames) > 1:
                lines.append(f"define_size = {nominal}, {name}, {max(1, frame.delay)}")
            else:
                lines.append(f"define_size = {nominal}, {name}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("meta.hl", "\n".join(lines) + "\n")
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Preference and environment
# --------------------------------------------------------------------------

def read_preference(path: Path = DMS_SETTINGS) -> tuple[str, int]:
    try:
        cursor = json.loads(path.read_text(encoding="utf-8")).get("cursorSettings", {})
    except (OSError, json.JSONDecodeError):
        cursor = {}
    theme = cursor.get("theme") or FALLBACK_THEME
    size = cursor.get("size")
    if not isinstance(size, int) or not 8 <= size <= 256:
        size = FALLBACK_SIZE
    return theme, size


def monitor_scales() -> set[float]:
    try:
        output = subprocess.run(
            ["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        return {float(monitor["scale"]) for monitor in json.loads(output)}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return set()


def target_sizes(size: int, scales: set[float]) -> list[int]:
    """The preferred size and its physical size on every relevant scale.

    Smaller sizes are deliberately omitted: a client that asks for a default
    such as 24 then resolves to the preferred size instead of a smaller one.
    """
    return sorted({round(size * scale) for scale in set(BASE_SCALES) | scales if scale >= 1})


def find_xcursor_theme(theme: str) -> Path | None:
    for base in XCURSOR_USER_DIRS:
        if (base / theme / "cursors").is_dir():
            return base / theme
    return None


def find_hyprcursor_theme(theme: str) -> Path | None:
    for base in XCURSOR_USER_DIRS:
        if (base / theme / "manifest.hl").is_file():
            return base / theme
    return None


# --------------------------------------------------------------------------
# Asset generation
# --------------------------------------------------------------------------

def snapshot_source(theme_dir: Path, hypr_dir: Path | None, source_dir: Path) -> None:
    """Copy the original art once; later runs always resample from it."""
    if source_dir.exists():
        return
    if (theme_dir / GENERATED_MARKER).exists():
        raise RuntimeError(
            f"{theme_dir} was generated by this script but its source snapshot "
            f"{source_dir} is missing; reinstall the original theme first"
        )
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=source_dir.parent, prefix=".snapshot-"))
    shutil.copytree(theme_dir / "cursors", staging / "cursors", symlinks=True)
    if hypr_dir is not None:
        shutil.copytree(hypr_dir, staging / "hyprcursor", symlinks=True)
    staging.rename(source_dir)


def source_digest(source_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((source_dir / "cursors").iterdir()):
        digest.update(path.name.encode())
        digest.update(os.readlink(path).encode() if path.is_symlink() else path.read_bytes())
    return digest.hexdigest()


def replace_dir(target: Path, build) -> None:
    """Build a sibling directory and swap it in, so readers never see a half-written theme."""
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}-"))
    try:
        build(staging)
        previous = target.with_name(f".{target.name}-old")
        if previous.exists():
            shutil.rmtree(previous)
        if target.exists():
            target.rename(previous)
        staging.rename(target)
        if previous.exists():
            shutil.rmtree(previous)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def generate_assets(theme_dir: Path, hypr_dir: Path | None, source_dir: Path, sizes: list[int]) -> int:
    sources = {}
    links = {}
    for path in sorted((source_dir / "cursors").iterdir()):
        if path.is_symlink():
            links[path.name] = os.readlink(path)
        else:
            sources[path.name] = largest_frames(read_xcursor(path.read_bytes()))
    scaled = {
        name: {size: [scale_frame(frame, size) for frame in frames] for size in sizes}
        for name, frames in sources.items()
    }

    def build_xcursor(staging: Path) -> None:
        for name, by_size in scaled.items():
            (staging / name).write_bytes(write_xcursor([f for size in sizes for f in by_size[size]]))
        for name, target in links.items():
            (staging / name).symlink_to(target)

    replace_dir(theme_dir / "cursors", build_xcursor)
    (theme_dir / GENERATED_MARKER).write_text(
        "Generated by dotfiles scripts/cursor_sync.py; original art is in\n"
        f"{source_dir}\n",
        encoding="utf-8",
    )

    if hypr_dir is not None:
        manifest = (hypr_dir / "manifest.hl").read_text(encoding="utf-8")
        match = re.search(r"^\s*cursors_directory\s*=\s*(\S+)", manifest, re.MULTILINE)
        cursors_dir = hypr_dir / (match.group(1) if match else "hyprcursors")

        def build_hyprcursor(staging: Path) -> None:
            for name, by_size in scaled.items():
                (staging / f"{name}.hlc").write_bytes(hyprcursor_archive(sources[name], by_size))
            for name, target in links.items():
                if target in scaled:
                    (staging / f"{name}.hlc").symlink_to(f"{target}.hlc")

        replace_dir(cursors_dir, build_hyprcursor)
    return len(scaled)


# --------------------------------------------------------------------------
# Consumers
# --------------------------------------------------------------------------

def run(command: list[str]) -> str | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def set_ini_keys(text: str, values: dict[str, str], separator: str) -> str:
    lines = text.splitlines()
    for key, value in values.items():
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*{re.escape(separator.strip())}")
        line = f"{key}{separator}{value}"
        for index, existing in enumerate(lines):
            if pattern.match(existing):
                lines[index] = line
                break
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


class Consumers:
    """Each consumer has a check (returns drift or None) and an apply."""

    def __init__(self, theme: str, size: int):
        self.theme = theme
        self.size = size

    def gsettings(self, apply: bool) -> str | None:
        schema = "org.gnome.desktop.interface"
        current = (run(["gsettings", "get", schema, "cursor-theme"]), run(["gsettings", "get", schema, "cursor-size"]))
        if current == (None, None):
            return None  # GSettings unavailable
        wanted = (f"'{self.theme}'", str(self.size))
        if current == wanted:
            return None
        if apply:
            run(["gsettings", "set", schema, "cursor-theme", self.theme])
            run(["gsettings", "set", schema, "cursor-size", str(self.size)])
        return f"GSettings cursor is {current[0]} {current[1]}"

    def default_theme(self, apply: bool) -> str | None:
        wanted = f"[Icon Theme]\nInherits={self.theme}\n"
        try:
            current = DEFAULT_THEME_INDEX.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if f"Inherits={self.theme}" in current.splitlines():
            return None
        if apply:
            DEFAULT_THEME_INDEX.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_THEME_INDEX.write_text(wanted, encoding="utf-8")
        return "default Xcursor theme does not inherit the selected theme"

    def xresources(self, apply: bool) -> str | None:
        values = {"Xcursor.theme": self.theme, "Xcursor.size": str(self.size)}
        try:
            current = XRESOURCES.read_text(encoding="utf-8")
        except OSError:
            current = ""
        updated = set_ini_keys(current, values, ": ") if current else "".join(f"{k}: {v}\n" for k, v in values.items())
        loaded = run(["xrdb", "-query"]) if os.environ.get("DISPLAY") else None
        stale_server = loaded is not None and any(f"{k}:\t{v}" not in loaded for k, v in values.items())
        if updated == current and not stale_server:
            return None
        if apply:
            if updated != current:
                XRESOURCES.write_text(updated, encoding="utf-8")
            if loaded is not None:
                run(["xrdb", "-merge", str(XRESOURCES)])
        return "Xresources cursor values are missing or not loaded in XWayland"

    def flatpak(self, apply: bool) -> str | None:
        if shutil.which("flatpak") is None:
            return None
        current = run(["flatpak", "override", "--user", "--show"]) or ""
        wanted = [f"XCURSOR_THEME={self.theme}", f"XCURSOR_SIZE={self.size}"]
        if all(line in current.splitlines() for line in wanted):
            return None
        if apply:
            run(["flatpak", "override", "--user", *[f"--env={value}" for value in wanted]])
        return "Flatpak cursor environment differs"

    def dms_module(self, apply: bool) -> str | None:
        # DMS owns this file; only report when it disagrees with its own settings.
        try:
            text = DMS_CURSOR_LUA.read_text(encoding="utf-8")
        except OSError:
            return None
        if f'"XCURSOR_SIZE", "{self.size}"' in text and f'"XCURSOR_THEME", "{self.theme}"' in text:
            return None
        return "DMS cursor.lua is stale (owned by DMS, not changed here); reselect the cursor in DMS settings"

    def all(self, apply: bool) -> list[str]:
        checks = (self.gsettings, self.default_theme, self.xresources, self.flatpak, self.dms_module)
        return [drift for check in checks if (drift := check(apply))]


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def load_stamp() -> dict:
    try:
        return json.loads(STAMP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report drift; exit 1 if any")
    mode.add_argument("--apply", action="store_true", help="regenerate assets and fix drift")
    parser.add_argument("--force", action="store_true", help="regenerate assets even if unchanged")
    args = parser.parse_args(argv)

    theme, size = read_preference()
    scales = monitor_scales()
    sizes = target_sizes(size, scales)
    print(f"cursor: {theme} {size}px; image sizes {sizes}")

    drift = []
    theme_dir = find_xcursor_theme(theme)
    regenerated = False
    if theme_dir is None:
        print(f"note: {theme} is not a user-installed Xcursor theme; its assets are left as installed")
    else:
        hypr_dir = find_hyprcursor_theme(theme)
        source_dir = SOURCE_ROOT / theme
        stamp = load_stamp()
        wanted = {"theme": theme, "sizes": sizes, "version": GENERATOR_VERSION}
        if source_dir.exists():
            wanted["source"] = source_digest(source_dir)
        if args.force or {k: stamp.get(k) for k in wanted} != wanted:
            drift.append(f"theme images are not generated for {sizes}")
            if args.apply:
                snapshot_source(theme_dir, hypr_dir, source_dir)
                wanted["source"] = source_digest(source_dir)
                count = generate_assets(theme_dir, hypr_dir, source_dir, sizes)
                STAMP.parent.mkdir(parents=True, exist_ok=True)
                STAMP.write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")
                regenerated = True
                formats = "Xcursor + Hyprcursor" if hypr_dir else "Xcursor"
                print(f"generated {count} cursors ({formats}) in {theme_dir}")

    drift += Consumers(theme, size).all(args.apply)

    if regenerated and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        # Hyprland caches the loaded theme; reload it with the new images.
        run(["hyprctl", "setcursor", theme, str(size)])

    for item in drift:
        print(("fixed: " if args.apply else "drift: ") + item)
    if not drift:
        print("all cursor consumers agree")
    return 1 if args.check and drift else 0


if __name__ == "__main__":
    sys.exit(main())
