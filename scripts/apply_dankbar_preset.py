#!/usr/bin/env python3
"""Apply the repository's compact DankBar profile to native DMS settings."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PRESET_PATH = ROOT / "dms/presets/dankbar-43pr.json"
THEME_SOURCE = ROOT / "dms/themes/graphite-slate/theme.json"
THEME_DIR_NAME = "dotfiles-graphite-slate"
DMS_SETTING_DEFAULTS = {
    "showWorkspaceName": False,
    "showWorkspacePadding": False,
    "showWorkspaceApps": False,
    "workspaceScrolling": False,
    "workspaceUnfocusedColorMode": "default",
    "workspaceUrgentColorMode": "default",
    "workspaceFocusedBorderColor": "primary",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def backup_path(settings_path: Path) -> Path:
    candidate = settings_path.with_name(settings_path.name + ".before-phase20")
    suffix = 1
    while candidate.exists():
        candidate = settings_path.with_name(settings_path.name + f".before-phase20.{suffix}")
        suffix += 1
    return candidate


def desired_settings(settings: dict[str, Any], preset: dict[str, Any], theme_path: Path) -> dict[str, Any]:
    if not isinstance(settings, dict) or not isinstance(preset, dict) or not isinstance(preset.get("settings"), dict):
        raise ValueError("DMS settings and DankBar preset must be JSON objects")
    updated = json.loads(json.dumps(settings))
    updates = preset["settings"]
    for key, value in updates.items():
        if key != "bar":
            updated[key] = value
    updated["customThemeFile"] = str(theme_path)

    bars = updated.get("barConfigs")
    if not isinstance(bars, list):
        raise ValueError("DMS settings must contain a barConfigs array")
    matching = [bar for bar in bars if isinstance(bar, dict) and bar.get("id") == updates["bar"]["id"]]
    if len(matching) != 1:
        raise ValueError("expected exactly one DMS bar config with id 'default'")
    matching[0].update(updates["bar"])
    return updated


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def apply(settings_path: Path, theme_dir: Path) -> tuple[Path, bool, Path | None]:
    settings_bytes = settings_path.read_bytes()
    settings = json.loads(settings_bytes)
    preset = read_json(PRESET_PATH)
    theme_bytes = THEME_SOURCE.read_bytes()
    theme_data = json.loads(theme_bytes)
    if not isinstance(settings, dict) or not isinstance(theme_data, dict):
        raise ValueError("DMS settings and generated theme must be JSON objects")

    theme_path = theme_dir / THEME_DIR_NAME / "theme.json"
    if theme_path.exists() and theme_path.read_bytes() != theme_bytes:
        raise ValueError(f"refusing to replace a different theme already at {theme_path}")

    updated = desired_settings(settings, preset, theme_path)
    updated_bytes = (json.dumps(updated, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    changed = updated_bytes != settings_bytes or not theme_path.exists()
    if not changed:
        return theme_path, False, None

    saved_copy = backup_path(settings_path)
    with saved_copy.open("xb") as stream:
        stream.write(settings_bytes)
        stream.flush()
        os.fsync(stream.fileno())

    if not theme_path.exists():
        write_atomic(theme_path, theme_bytes)
    write_atomic(settings_path, updated_bytes)
    return theme_path, True, saved_copy


def check(settings_path: Path, theme_dir: Path) -> bool:
    try:
        settings = read_json(settings_path)
        preset = read_json(PRESET_PATH)
        theme_path = theme_dir / THEME_DIR_NAME / "theme.json"
        expected = desired_settings(settings, preset, theme_path)
        actual_config = json.loads(json.dumps(settings))
        actual_config["customThemeFile"] = str(theme_path)
        for key, value in DMS_SETTING_DEFAULTS.items():
            if key not in actual_config:
                actual_config[key] = value
        return actual_config == expected and theme_path.is_file() and theme_path.read_bytes() == THEME_SOURCE.read_bytes()
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--apply", action="store_true", help="install the theme and merge the DankBar profile (stop DMS first)")
    actions.add_argument("--check", action="store_true", help="check whether the profile and theme are installed")
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path.home() / ".config/DankMaterialShell/settings.json",
        help="DMS settings file (defaults to the current user's settings)",
    )
    parser.add_argument(
        "--theme-dir",
        type=Path,
        default=Path.home() / ".config/DankMaterialShell/themes",
        help="DMS custom themes directory",
    )
    args = parser.parse_args()

    try:
        if args.check:
            if check(args.settings, args.theme_dir):
                print("DankBar preset and Graphite Slate DMS theme are installed")
                return 0
            print("DankBar preset or Graphite Slate DMS theme is not installed")
            return 1
        theme_path, changed, saved_copy = apply(args.settings, args.theme_dir)
        if changed:
            print(f"DankBar preset applied; settings backup: {saved_copy}")
        else:
            print("DankBar preset already applied")
        print(f"DMS custom theme: {theme_path}")
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
