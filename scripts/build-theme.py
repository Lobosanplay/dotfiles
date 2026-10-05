#!/usr/bin/env python3
"""Validate the semantic theme preset and render component theme outputs."""

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
DMS_TEMPLATE_PATH = ROOT / "themes/templates/dms-theme.json.tmpl"
DMS_OUTPUT_PATH = ROOT / "dms/themes/graphite-slate/theme.json"
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PLACEHOLDER_RE = re.compile(r"@@([a-z_]+\.[a-z_]+?)(?:_(hex))?@@")
REQUIRED_TOKEN_GROUPS = {
    "surfaces": {"background", "surface", "surface_variant", "surface_elevated"},
    "text": {"primary", "secondary", "muted", "disabled"},
    "accents": {"primary", "secondary", "selection", "focus"},
    "semantic": {"success", "warning", "error", "info"},
    "borders": {"default", "subtle"},
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        try:
            display_path = path.relative_to(ROOT)
        except ValueError:
            display_path = path
        raise ValueError(f"cannot read {display_path}: {exc}") from exc


def validate_theme(preset: Any, schema: Any) -> list[str]:
    errors: list[str] = []

    if not isinstance(preset, dict):
        return ["preset root must be a JSON object"]
    expected_top_level = {"schema_version", "id", "name", "mode", "tokens", "typography", "iconography"}
    if set(preset) != expected_top_level:
        errors.append("preset has missing or unexpected top-level fields")
    if preset.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if not isinstance(preset.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", preset["id"]):
        errors.append("id must contain lowercase letters, digits, and hyphens")
    if not isinstance(preset.get("name"), str) or not preset["name"].strip():
        errors.append("name must be a non-empty string")
    if preset.get("mode") != "dark":
        errors.append("mode must be 'dark' for schema version 1")

    tokens = preset.get("tokens")
    if not isinstance(tokens, dict) or set(tokens) != set(REQUIRED_TOKEN_GROUPS):
        errors.append(f"tokens must contain exactly: {', '.join(REQUIRED_TOKEN_GROUPS)}")
        tokens = tokens if isinstance(tokens, dict) else {}

    for group, required in REQUIRED_TOKEN_GROUPS.items():
        values = tokens.get(group)
        if not isinstance(values, dict) or set(values) != required:
            errors.append(f"tokens.{group} must contain exactly: {', '.join(sorted(required))}")
            continue
        for key, value in values.items():
            if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
                errors.append(f"tokens.{group}.{key} must be opaque #RRGGBB")

    errors.extend(validate_typography(preset.get("typography")))
    errors.extend(validate_iconography(preset.get("iconography")))

    if isinstance(schema, dict):
        schema_properties = schema.get("properties", {})
        if set(schema.get("required", [])) != expected_top_level:
            errors.append("schema required fields do not match the preset contract")
        if schema_properties.get("schema_version", {}).get("const") != 2:
            errors.append("schema does not describe schema_version 2")
        token_schema = schema_properties.get("tokens", {})
        token_properties = token_schema.get("properties", {})
        if set(token_properties) != set(REQUIRED_TOKEN_GROUPS):
            errors.append("schema token groups do not match the validator contract")
        if set(token_schema.get("required", [])) != set(REQUIRED_TOKEN_GROUPS):
            errors.append("schema must require every semantic token group")
        for group, roles in REQUIRED_TOKEN_GROUPS.items():
            group_schema = token_properties.get(group, {})
            if set(group_schema.get("required", [])) != roles:
                errors.append(f"schema required roles do not match tokens.{group}")
        color_schema = schema.get("$defs", {}).get("colorGroup", {})
        if color_schema.get("patternProperties", {}).get("^[a-z][a-z0-9_]*$", {}).get("pattern") != COLOR_RE.pattern:
            errors.append("schema color values must use the opaque #RRGGBB contract")
        typography_schema = schema_properties.get("typography", {})
        if set(typography_schema.get("required", [])) != {"families", "scale_unit", "scale", "weights", "line_height"}:
            errors.append("schema typography roles do not match the preset contract")
        iconography_schema = schema_properties.get("iconography", {})
        if set(iconography_schema.get("required", [])) != {"provider", "family", "source", "symbol_format", "api", "aliases", "fallback"}:
            errors.append("schema icon roles do not match the preset contract")
        overlay_schema = schema.get("$defs", {}).get("dynamicColorOverlay", {})
        if set(overlay_schema.get("required", [])) != {"schema_version", "source", "mode", "tokens"}:
            errors.append("schema dynamic color overlay does not match the runtime contract")
        overlay_tokens = overlay_schema.get("properties", {}).get("tokens", {}).get("properties", {})
        if set(overlay_tokens) != set(REQUIRED_TOKEN_GROUPS):
            errors.append("schema dynamic overlay groups do not match the semantic contract")
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


def validate_typography(typography: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(typography, dict) or set(typography) != {"families", "scale_unit", "scale", "weights", "line_height"}:
        return ["typography must define families, scale_unit, scale, weights, and line_height"]

    families = typography["families"]
    if not isinstance(families, dict) or set(families) != {"ui", "mono"}:
        errors.append("typography.families must define ui and mono")
    else:
        for role, family in families.items():
            if not isinstance(family, dict) or set(family) != {"primary", "source", "fallback"}:
                errors.append(f"typography.families.{role} has an invalid shape")
                continue
            if not isinstance(family["primary"], str) or not family["primary"].strip():
                errors.append(f"typography.families.{role}.primary must be a non-empty family name")
            if not isinstance(family["source"], str) or not family["source"].strip():
                errors.append(f"typography.families.{role}.source must be documented")
            fallback = family["fallback"]
            if (
                not isinstance(fallback, list)
                or not fallback
                or any(not isinstance(item, str) or not item.strip() for item in fallback)
                or len(set(fallback)) != len(fallback)
            ):
                errors.append(f"typography.families.{role}.fallback must be a non-empty unique list")

    expected_sizes = {"display", "title", "heading", "body", "label", "caption", "micro"}
    scale = typography["scale"]
    if not isinstance(scale, dict) or set(scale) != expected_sizes:
        errors.append("typography.scale must define display, title, heading, body, label, caption, and micro")
    elif any(type(size) is not int or not 8 <= size <= 64 for size in scale.values()):
        errors.append("typography.scale values must be integer logical pixels between 8 and 64")
    elif list(scale.values()) != sorted(scale.values(), reverse=True):
        errors.append("typography.scale must descend from display to micro")

    expected_weights = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700}
    if typography["weights"] != expected_weights:
        errors.append("typography.weights must map regular/medium/semibold/bold to 400/500/600/700")

    expected_line_heights = {"compact", "normal", "relaxed"}
    line_height = typography["line_height"]
    if not isinstance(line_height, dict) or set(line_height) != expected_line_heights:
        errors.append("typography.line_height must define compact, normal, and relaxed")
    elif any(type(value) not in (int, float) or not 1 < value <= 2 for value in line_height.values()):
        errors.append("typography.line_height values must be ratios greater than 1 and at most 2")
    elif list(line_height.values()) != sorted(line_height.values()):
        errors.append("typography.line_height must increase from compact to relaxed")

    if typography["scale_unit"] != "logical-px":
        errors.append("typography.scale_unit must be logical-px")
    return errors


def validate_iconography(iconography: Any) -> list[str]:
    expected_fields = {"provider", "family", "source", "symbol_format", "api", "aliases", "fallback"}
    if not isinstance(iconography, dict) or set(iconography) != expected_fields:
        return ["iconography has missing or unexpected fields"]

    errors: list[str] = []
    expected = {
        "provider": "material-symbols-rounded",
        "family": "Material Symbols Rounded",
        "source": "DMS-bundled",
        "symbol_format": "lowercase-ligature-name",
        "api": {
            "DankIcon.name": "<ligature-name>",
            "AppIconRenderer.iconValue": "material:<ligature-name>",
        },
    }
    for key, value in expected.items():
        if iconography.get(key) != value:
            errors.append(f"iconography.{key} does not match the DMS Material Symbols contract")

    aliases = iconography["aliases"]
    if (
        not isinstance(aliases, dict)
        or not aliases
        or any(not re.fullmatch(r"[a-z][a-z0-9_]*", key) for key in aliases)
        or any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value) for value in aliases.values())
        or len(set(aliases.values())) != len(aliases)
    ):
        errors.append("iconography.aliases must map unique semantic ids to lowercase Material ligature names")
    if not isinstance(iconography["fallback"], str) or not iconography["fallback"].strip():
        errors.append("iconography.fallback must describe the system-icon fallback strategy")
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

    template = template.replace("@@typography_lua@@", lua_literal(preset["typography"], indent=4))
    template = template.replace("@@iconography_lua@@", lua_literal(preset["iconography"], indent=4))
    rendered = PLACEHOLDER_RE.sub(substitute, template)
    if "@@" in rendered:
        raise ValueError("template contains an unsupported or unresolved placeholder")
    return rendered


def render_dms_theme(preset: dict[str, Any], template: str) -> str:
    flat = {
        f"{group}.{key}": value
        for group, values in preset["tokens"].items()
        for key, value in values.items()
    }
    rendered = template.replace("@@theme_name_json@@", json.dumps(preset["name"]))

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        as_hex = match.group(2)
        try:
            value = flat[key]
        except KeyError as exc:
            raise ValueError(f"DMS theme template references missing token: {key}") from exc
        return value[1:] if as_hex else value

    rendered = PLACEHOLDER_RE.sub(substitute, rendered)
    if "@@" in rendered:
        raise ValueError("DMS theme template contains an unsupported or unresolved placeholder")
    # Validate that the template remains valid JSON before writing it.
    json.loads(rendered)
    return rendered


def lua_literal(value: Any, indent: int = 0) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        entries = [" " * (indent + 4) + lua_literal(item, indent + 4) + "," for item in value]
        return "{}" if not entries else "{\n" + "\n".join(entries) + "\n" + " " * indent + "}"
    if isinstance(value, dict):
        entries = []
        for key, item in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                rendered_key = "[" + lua_literal(key, indent + 4) + "]"
            else:
                rendered_key = key
            entries.append(
                " " * (indent + 4)
                + rendered_key
                + " = "
                + lua_literal(item, indent + 4)
                + ","
            )
        return "{}" if not entries else "{\n" + "\n".join(entries) + "\n" + " " * indent + "}"
    raise ValueError(f"unsupported token type for Lua output: {type(value).__name__}")


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
    action.add_argument("--check-dynamic", metavar="FILE", help="validate a Matugen semantic color overlay")
    args = parser.parse_args()

    try:
        if args.check_dynamic:
            dynamic = read_json(Path(args.check_dynamic).resolve())
            errors = validate_dynamic_theme(dynamic)
            if errors:
                raise ValueError("invalid dynamic theme:\n- " + "\n- ".join(errors))
            print("dynamic semantic color overlay is valid")
            return 0

        rendered = load_and_render()
        preset = read_json(PRESET_PATH)
        dms_rendered = render_dms_theme(preset, DMS_TEMPLATE_PATH.read_text(encoding="utf-8"))
        if args.write:
            OUTPUT_PATH.write_text(rendered, encoding="utf-8")
            DMS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            DMS_OUTPUT_PATH.write_text(dms_rendered, encoding="utf-8")
            print(f"generated {OUTPUT_PATH.relative_to(ROOT)}")
            print(f"generated {DMS_OUTPUT_PATH.relative_to(ROOT)}")
            return 0
        current = OUTPUT_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(f"{OUTPUT_PATH.relative_to(ROOT)} is missing or out of date; run scripts/build-theme.py --write", file=sys.stderr)
            return 1
        current_dms = DMS_OUTPUT_PATH.read_text(encoding="utf-8")
        if current_dms != dms_rendered:
            print(f"{DMS_OUTPUT_PATH.relative_to(ROOT)} is missing or out of date; run scripts/build-theme.py --write", file=sys.stderr)
            return 1
        print("theme contract valid; generated Hyprland and DMS theme outputs are current")
        return 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


def validate_dynamic_theme(theme: Any) -> list[str]:
    """Validate the color-only overlay emitted by the DMS Matugen template."""
    if not isinstance(theme, dict) or set(theme) != {"schema_version", "source", "mode", "tokens"}:
        return ["dynamic theme must contain exactly schema_version, source, mode, and tokens"]

    errors: list[str] = []
    if theme["schema_version"] != 2:
        errors.append("schema_version must match the semantic theme contract version 2")
    if theme["source"] != "dms-matugen":
        errors.append("source must be dms-matugen")
    if theme["mode"] != "dark":
        errors.append("mode must be dark")

    tokens = theme["tokens"]
    if not isinstance(tokens, dict) or set(tokens) != set(REQUIRED_TOKEN_GROUPS):
        return errors + ["tokens must contain exactly the semantic color groups"]

    for group, required in REQUIRED_TOKEN_GROUPS.items():
        values = tokens[group]
        if not isinstance(values, dict) or set(values) != required:
            errors.append(f"tokens.{group} must contain exactly: {', '.join(sorted(required))}")
            continue
        for role, value in values.items():
            if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
                errors.append(f"tokens.{group}.{role} must be opaque #RRGGBB")

    if not errors:
        background = tokens["surfaces"]["background"]
        text = tokens["text"]
        if contrast_ratio(text["primary"], background) < 7.0:
            errors.append("tokens.text.primary must have at least 7:1 contrast against the background")
        if contrast_ratio(text["secondary"], background) < 4.5:
            errors.append("tokens.text.secondary must have at least 4.5:1 contrast against the background")
        if contrast_ratio(text["muted"], background) < 3.0:
            errors.append("tokens.text.muted must have at least 3:1 contrast against the background")

    return errors


if __name__ == "__main__":
    raise SystemExit(main())
