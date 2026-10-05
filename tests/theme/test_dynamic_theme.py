import importlib.util
import json
import shutil
import shlex
import struct
import subprocess
import tempfile
import tomllib
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "matugen/.config/matugen/templates/dynamic-colors.json.tmpl"
PROMOTER = ROOT / "scripts/promote_dynamic_theme.py"
MATUGEN_CONFIG = ROOT / "matugen/.config/matugen/config.toml"

spec = importlib.util.spec_from_file_location("build_theme", ROOT / "scripts/build-theme.py")
build_theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_theme)


def png_chunk(kind, data):
    return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_test_wallpaper(path):
    width = height = 32
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend((20 + x * 5, 40 + y * 3, 90 + ((x + y) % 16) * 4))
        rows.append(bytes(row))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


class DynamicThemeTests(unittest.TestCase):
    def test_matugen_config_registers_only_a_user_template(self):
        config = tomllib.loads(MATUGEN_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(set(config["templates"]), {"dotfiles_semantic_colors"})
        template = config["templates"]["dotfiles_semantic_colors"]
        self.assertIn("dynamic-colors.json.tmpl", template["input_path"])
        self.assertIn("dynamic-colors.pending.json", template["output_path"])
        self.assertNotIn("theme_tokens.lua", template["output_path"])
        self.assertIn("promote_dynamic_theme.py", template["post_hook"])
        self.assertNotIn("matugen image", template["post_hook"])

    def test_dynamic_overlay_schema_reuses_contract_role_groups(self):
        schema = json.loads((ROOT / "themes/tokens/schema.json").read_text(encoding="utf-8"))
        overlay = schema["$defs"]["dynamicColorOverlay"]
        self.assertEqual(
            set(overlay["required"]),
            {"schema_version", "source", "mode", "tokens"},
        )
        groups = overlay["properties"]["tokens"]["properties"]
        self.assertEqual(set(groups), set(build_theme.REQUIRED_TOKEN_GROUPS))
        for group, roles in build_theme.REQUIRED_TOKEN_GROUPS.items():
            self.assertEqual(set(groups[group]["required"]), roles)

    def test_dynamic_overlay_validator_rejects_invalid_color_and_contrast(self):
        invalid_color = {
            "schema_version": 2,
            "source": "dms-matugen",
            "mode": "dark",
            "tokens": {group: {role: "#ffffff" for role in roles} for group, roles in build_theme.REQUIRED_TOKEN_GROUPS.items()},
        }
        invalid_color["tokens"]["surfaces"]["background"] = "blue"
        self.assertTrue(build_theme.validate_dynamic_theme(invalid_color))

        low_contrast = json.loads(json.dumps(invalid_color))
        low_contrast["tokens"]["surfaces"]["background"] = "#ffffff"
        low_contrast["tokens"]["text"]["primary"] = "#ffffff"
        low_contrast["tokens"]["text"]["secondary"] = "#ffffff"
        low_contrast["tokens"]["text"]["muted"] = "#ffffff"
        self.assertTrue(any("contrast" in error for error in build_theme.validate_dynamic_theme(low_contrast)))

    @unittest.skipUnless(shutil.which("matugen"), "matugen is not installed")
    def test_matugen_generates_and_promotes_valid_overlay_atomically(self):
        with tempfile.TemporaryDirectory(prefix="theme-dynamic-test-") as temp_dir:
            temp = Path(temp_dir)
            wallpaper = temp / "wallpaper.png"
            write_test_wallpaper(wallpaper)
            candidate = temp / "candidate.json"
            output = temp / "dynamic-colors.json"
            config = temp / "matugen.toml"
            dank16 = {
                "dank16": {
                    f"color{index}": {
                        "dark": {"hex": f"#{index:02x}{(255 - index):02x}80"}
                    }
                    for index in range(16)
                }
            }
            hook = shlex.join([
                "python3",
                str(PROMOTER),
                "--candidate",
                str(candidate),
                "--output",
                str(output),
            ])
            config.write_text(
                "[config]\n"
                "[templates.dynamic]\n"
                f"input_path = {json.dumps(str(TEMPLATE))}\n"
                f"output_path = {json.dumps(str(candidate))}\n"
                f"post_hook = {json.dumps(hook)}\n",
                encoding="utf-8",
            )
            command = [
                "matugen", "image", str(wallpaper), "--config", str(config),
                "--mode", "dark", "--type", "scheme-tonal-spot",
                "--source-color-index", "0", "--import-json-string",
                json.dumps(dank16), "--quiet",
            ]
            generated = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertFalse(candidate.exists(), "successful promotion should consume the pending file")
            self.assertTrue(output.is_file())
            active = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(build_theme.validate_dynamic_theme(active), [])
            last_known_good = output.read_bytes()

            invalid_wallpaper = temp / "invalid.png"
            invalid_wallpaper.write_text("not an image", encoding="utf-8")
            failed = subprocess.run(
                ["matugen", "image", str(invalid_wallpaper), "--config", str(config), "--mode", "dark", "--quiet"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(output.read_bytes(), last_known_good)

            candidate.write_text(json.dumps({"schema_version": 2, "source": "dms-matugen", "mode": "dark", "tokens": {}}), encoding="utf-8")
            rejected = subprocess.run(
                ["python3", str(PROMOTER), "--candidate", str(candidate), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(output.read_bytes(), last_known_good)


if __name__ == "__main__":
    unittest.main()
