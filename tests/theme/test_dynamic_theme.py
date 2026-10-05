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
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "matugen/.config/matugen/templates/dynamic-colors.json.tmpl"
PROMOTER = ROOT / "scripts/promote_dynamic_theme.py"
MATUGEN_CONFIG = ROOT / "matugen/.config/matugen/config.toml"

spec = importlib.util.spec_from_file_location("build_theme", ROOT / "scripts/build-theme.py")
build_theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_theme)
promoter_spec = importlib.util.spec_from_file_location("promote_dynamic_theme", PROMOTER)
promoter = importlib.util.module_from_spec(promoter_spec)
promoter_spec.loader.exec_module(promoter)


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

    def test_dynamic_overlay_validator_rejects_missing_unknown_and_wrongly_typed_roles(self):
        valid = {
            "schema_version": 2,
            "source": "dms-matugen",
            "mode": "dark",
            "tokens": {
                group: {role: "#aabbcc" for role in roles}
                for group, roles in build_theme.REQUIRED_TOKEN_GROUPS.items()
            },
        }
        missing = json.loads(json.dumps(valid))
        del missing["tokens"]["semantic"]["info"]
        self.assertTrue(build_theme.validate_dynamic_theme(missing))

        unknown = json.loads(json.dumps(valid))
        unknown["tokens"]["semantic"]["unknown"] = "#aabbcc"
        self.assertTrue(build_theme.validate_dynamic_theme(unknown))

        wrong_type = json.loads(json.dumps(valid))
        wrong_type["tokens"]["semantic"]["info"] = 17
        self.assertTrue(build_theme.validate_dynamic_theme(wrong_type))

    @unittest.skipUnless(shutil.which("matugen"), "matugen is not installed")
    def test_matugen_generates_and_promotes_valid_overlay_atomically(self):
        with tempfile.TemporaryDirectory(prefix="theme-dynamic-test-") as temp_dir:
            temp = Path(temp_dir)
            wallpaper = temp / "wallpaper.png"
            write_test_wallpaper(wallpaper)
            candidate = temp / "candidate.json"
            output = temp / "dynamic-colors.json"
            runtime_lua = temp / "dotfiles_theme.lua"
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
                "--runtime-lua",
                str(runtime_lua),
                "--apply-live",
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
            self.assertTrue(runtime_lua.is_file())
            active = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(build_theme.validate_dynamic_theme(active), [])
            rendered = runtime_lua.read_text(encoding="utf-8")
            self.assertIn(f'rgb({active["tokens"]["accents"]["primary"][1:]})', rendered)
            self.assertIn(f'rgb({active["tokens"]["borders"]["default"][1:]})', rendered)
            last_known_good = output.read_bytes()
            last_runtime = runtime_lua.read_bytes()

            invalid_wallpaper = temp / "invalid.png"
            invalid_wallpaper.write_text("not an image", encoding="utf-8")
            failed = subprocess.run(
                ["matugen", "image", str(invalid_wallpaper), "--config", str(config), "--mode", "dark", "--quiet"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(output.read_bytes(), last_known_good)
            self.assertEqual(runtime_lua.read_bytes(), last_runtime)

            candidate.write_text(json.dumps({"schema_version": 2, "source": "dms-matugen", "mode": "dark", "tokens": {}}), encoding="utf-8")
            rejected = subprocess.run(
                ["python3", str(PROMOTER), "--candidate", str(candidate), "--output", str(output), "--runtime-lua", str(runtime_lua)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(output.read_bytes(), last_known_good)
            self.assertEqual(runtime_lua.read_bytes(), last_runtime)

    def test_runtime_lua_rendering_is_deterministic_and_uses_contract_roles(self):
        state = {
            "schema_version": 2,
            "source": "dms-matugen",
            "mode": "dark",
            "tokens": {
                group: {role: "#aabbcc" for role in roles}
                for group, roles in build_theme.REQUIRED_TOKEN_GROUPS.items()
            },
        }
        rendered = promoter.render_hyprland_lua(state)
        self.assertEqual(rendered, promoter.render_hyprland_lua(state))
        self.assertIn('active_border = "rgb(aabbcc)"', rendered)
        self.assertIn('border_locked_active = "rgb(aabbcc)"', rendered)
        self.assertNotIn("os.execute", rendered)

    def test_apply_existing_state_validates_before_writing_runtime_lua(self):
        with tempfile.TemporaryDirectory(prefix="theme-current-state-") as temp_dir:
            temp = Path(temp_dir)
            state = temp / "dynamic-colors.json"
            runtime_lua = temp / "hypr/dms/dotfiles_theme.lua"
            state.write_text(json.dumps({"schema_version": 2, "tokens": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                promoter.apply_existing(state, runtime_lua)
            self.assertFalse(runtime_lua.exists())

    def test_runtime_write_failure_restores_last_known_good_pair(self):
        with tempfile.TemporaryDirectory(prefix="theme-rollback-") as temp_dir:
            temp = Path(temp_dir)
            candidate = temp / "candidate.json"
            output = temp / "dynamic-colors.json"
            runtime_lua = temp / "dotfiles_theme.lua"
            previous = {
                "schema_version": 2,
                "source": "dms-matugen",
                "mode": "dark",
                "tokens": json.loads((ROOT / "themes/presets/default.json").read_text(encoding="utf-8"))["tokens"],
            }
            candidate_data = json.loads(json.dumps(previous))
            candidate_data["tokens"]["accents"]["primary"] = "#bbccee"
            candidate.write_text(json.dumps(candidate_data), encoding="utf-8")
            output.write_text(json.dumps(previous), encoding="utf-8")
            runtime_lua.write_text("previous lua module\n", encoding="utf-8")
            original_output = output.read_bytes()
            original_lua = runtime_lua.read_bytes()
            real_write_atomic = promoter.write_atomic

            def fail_new_runtime(path, content):
                if path == runtime_lua and content != original_lua:
                    raise OSError("simulated runtime module write error")
                return real_write_atomic(path, content)

            with mock.patch.object(promoter, "write_atomic", side_effect=fail_new_runtime):
                with self.assertRaisesRegex(OSError, "simulated"):
                    promoter.promote(candidate, output, runtime_lua)
            self.assertEqual(output.read_bytes(), original_output)
            self.assertEqual(runtime_lua.read_bytes(), original_lua)
            self.assertTrue(candidate.exists())

    def test_bridge_requires_active_hyprland_to_load_dms_module_and_consumer(self):
        with tempfile.TemporaryDirectory(prefix="theme-bridge-config-") as temp_dir:
            config = Path(temp_dir)
            (config / "modules").mkdir()
            (config / "hyprland.lua").write_text('require("modules.dms")\n')
            dms_module = config / "modules/dms.lua"
            dms_module.write_text('optional_require("dms.dotfiles_theme")\n')
            self.assertTrue(promoter.active_config_supports_bridge(config))
            dms_module.write_text('optional_require("dms.colors")\n')
            self.assertFalse(promoter.active_config_supports_bridge(config))


if __name__ == "__main__":
    unittest.main()
