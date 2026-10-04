#!/usr/bin/env python3
"""Validate the semantic theme preset and render its Hyprland Lua module."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PRESET_PATH = ROOT / "themes/presets/default.json"
SCHEMA_PATH = ROOT / "themes/tokens/schema.json"
TEMPLATE_PATH = ROOT / "themes/templates/hyprland-theme.lua.tmpl"
OUTPUT_PATH = ROOT / "hypr/.config/hypr/modules/theme_tokens.lua"
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PLACEHOLDER_RE = re.compile(r"@@([a-z_]+\.[a-z_]+?)(?:_(hex))?@@")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc


def validate_theme(preset: Any, schema: Any) -> list[str]:
    errors: list[str] = []
    required_groups = {
        "surfaces": {"background", "surface", "surface_variant", "surface_elevated"},
        "text": {"primary", "secondary", "muted", "disabled"},
        "accents": {"primary", "secondary", "selection", "focus"},
        "semantic": {"success", "warning", "error", "info"},
        "borders": {"default", "subtle"},
    }

    if not isinstance(preset, dict):
        return ["preset root must be a JSON object"]
    if set(preset) != {"schema_version", "id", "name", "mode", "tokens"}:
        errors.append("preset must contain exactly schema_version, id, name, mode, and tokens")
    if preset.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(preset.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", preset["id"]):
        errors.append("id must contain lowercase letters, digits, and hyphens")
    if not isinstance(preset.get("name"), str) or not preset["name"].strip():
        errors.append("name must be a non-empty string")
    if preset.get("mode") != "dark":
        errors.append("mode must be 'dark' for schema version 1")

    tokens = preset.get("tokens")
    if not isinstance(tokens, dict) or set(tokens) != set(required_groups):
        errors.append(f"tokens must contain exactly: {', '.join(required_groups)}")
        tokens = tokens if isinstance(tokens, dict) else {}

    for group, required in required_groups.items():
        values = tokens.get(group)
        if not isinstance(values, dict) or set(values) != required:
            errors.append(f"tokens.{group} must contain exactly: {', '.join(sorted(required))}")
            continue
        for key, value in values.items():
            if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
                errors.append(f"tokens.{group}.{key} must be opaque #RRGGBB")

    if isinstance(schema, dict):
        schema_properties = schema.get("properties", {})
        if schema_properties.get("schema_version", {}).get("const") != 1:
            errors.append("schema does not describe schema_version 1")
        token_schema = schema_properties.get("tokens", {})
        token_properties = token_schema.get("properties", {})
        if set(token_properties) != set(required_groups):
            errors.append("schema token groups do not match the validator contract")
        if set(token_schema.get("required", [])) != set(required_groups):
            errors.append("schema must require every semantic token group")
        for group, roles in required_groups.items():
            group_schema = token_properties.get(group, {})
            if set(group_schema.get("required", [])) != roles:
                errors.append(f"schema required roles do not match tokens.{group}")
        color_schema = schema.get("$defs", {}).get("colorGroup", {})
        if color_schema.get("patternProperties", {}).get("^[a-z][a-z0-9_]*$", {}).get("pattern") != COLOR_RE.pattern:
            errors.append("schema color values must use the opaque #RRGGBB contract")
    else:
        errors.append("schema root must be a JSON object")

    if not errors:
        text = tokens["text"]
        background = tokens["surfaces"]["background"]
        if contrast_ratio(text["primary"], background) < 7.0:
            errors.append("text.primary must have at least 7:1 contrast against surfaces.background")
        if contrast_ratio(text["secondary"], background) < 4.5:
            errors.append("text.secondary must have at least 4.5:1 contrast against surfaces.background")
        if contrast_ratio(text["muted"], background) < 3.0:
            errors.append("text.muted must have at least 3:1 contrast against surfaces.background")

    return errors


def linear_channel(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
    red, green, blue = (linear_channel(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    luminances = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (luminances[0] + 0.05) / (luminances[1] + 0.05)


def render_theme(preset: dict[str, Any], template: str) -> str:
    flat = {
        f"{group}.{key}": value
        for group, values in preset["tokens"].items()
        for key, value in values.items()
    }

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        as_hex = match.group(2)
        try:
            value = flat[key]
        except KeyError as exc:
            raise ValueError(f"template references missing token: {key}") from exc
        return value[1:] if as_hex else value

    rendered = PLACEHOLDER_RE.sub(substitute, template)
    if "@@" in rendered:
        raise ValueError("template contains an unsupported or unresolved placeholder")
    return rendered


def load_and_render() -> str:
    preset = read_json(PRESET_PATH)
    schema = read_json(SCHEMA_PATH)
    errors = validate_theme(preset, schema)
    if errors:
        raise ValueError("invalid theme preset:\n- " + "\n- ".join(errors))
    return render_theme(preset, TEMPLATE_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="render the generated Hyprland Lua module")
    action.add_argument("--check", action="store_true", help="validate inputs and check generated output is current")
    args = parser.parse_args()

    try:
        rendered = load_and_render()
        if args.write:
            OUTPUT_PATH.write_text(rendered, encoding="utf-8")
            print(f"generated {OUTPUT_PATH.relative_to(ROOT)}")
            return 0
        current = OUTPUT_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(f"{OUTPUT_PATH.relative_to(ROOT)} is missing or out of date; run scripts/build-theme.py --write", file=sys.stderr)
            return 1
        print("theme contract valid; generated Hyprland tokens are current")
        return 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
