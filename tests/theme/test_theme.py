import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("build_theme", ROOT / "scripts/build-theme.py")
build_theme = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_theme)


class ThemeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preset = json.loads((ROOT / "themes/presets/default.json").read_text())
        cls.schema = json.loads((ROOT / "themes/tokens/schema.json").read_text())
        cls.template = (ROOT / "themes/templates/hyprland-theme.lua.tmpl").read_text()

    def test_default_preset_matches_contract_and_contrast(self):
        self.assertEqual(build_theme.validate_theme(self.preset, self.schema), [])
        tokens = self.preset["tokens"]
        self.assertGreaterEqual(build_theme.contrast_ratio(tokens["text"]["primary"], tokens["surfaces"]["background"]), 7.0)
        self.assertGreaterEqual(build_theme.contrast_ratio(tokens["text"]["secondary"], tokens["surfaces"]["background"]), 4.5)

    def test_typography_roles_and_scale_are_well_formed(self):
        typography = self.preset["typography"]
        sizes = typography["scale"]
        self.assertEqual(list(sizes.values()), sorted(sizes.values(), reverse=True))
        self.assertEqual(typography["weights"], {"regular": 400, "medium": 500, "semibold": 600, "bold": 700})
        self.assertEqual(build_theme.validate_typography(typography), [])

    def test_selected_system_fallbacks_resolve(self):
        if not shutil.which("fc-match"):
            self.skipTest("fontconfig fc-match is not installed")
        for role, expected in (("ui", "Adwaita Sans"), ("mono", "Adwaita Mono")):
            fallback = self.preset["typography"]["families"][role]["fallback"][0]
            resolved = subprocess.run(
                ["fc-match", "-f", "%{family}", fallback],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(resolved, expected)

    def test_dms_bundled_fonts_and_material_ligatures_exist(self):
        assets = Path("/usr/share/quickshell/dms/DankCommon/assets/fonts")
        self.assertTrue((assets / "inter/InterVariable.ttf").is_file())
        self.assertTrue((assets / "nerd-fonts/FiraCodeNerdFont-Regular.ttf").is_file())
        material_font = next((assets / "material-design-icons/variablefont").glob("MaterialSymbolsRounded*.ttf"))
        if not shutil.which("hb-shape"):
            self.skipTest("hb-shape is not installed")
        aliases = self.preset["iconography"]["aliases"]
        self.assertEqual(build_theme.validate_iconography(self.preset["iconography"]), [])
        for symbol in aliases.values():
            shaped = subprocess.run(
                ["hb-shape", str(material_font), symbol],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertIn(f"[{symbol}=", shaped)

    def test_invalid_color_and_missing_required_role_are_rejected(self):
        invalid = json.loads(json.dumps(self.preset))
        invalid["tokens"]["accents"]["primary"] = "blue"
        invalid["tokens"]["semantic"].pop("warning")
        errors = build_theme.validate_theme(invalid, self.schema)
        self.assertTrue(any("opaque #RRGGBB" in error for error in errors))
        self.assertTrue(any("tokens.semantic" in error for error in errors))

    def test_hyprland_template_render_is_deterministic_and_complete(self):
        first = build_theme.render_theme(self.preset, self.template)
        second = build_theme.render_theme(self.preset, self.template)
        self.assertEqual(first, second)
        self.assertNotIn("@@", first)
        self.assertIn('active_border = {', first)
        self.assertIn('"rgba(8ab4f8ee)"', first)
        self.assertIn('inactive_border = "rgba(343b46aa)"', first)
        self.assertIn("shadow = 0xee0b0d11", first)
        self.assertIn('primary = "Inter Variable"', first)
        self.assertIn('["AppIconRenderer.iconValue"] = "material:<ligature-name>"', first)

    def test_dms_theme_output_maps_semantic_roles_and_is_valid_json(self):
        template = (ROOT / "themes/templates/dms-theme.json.tmpl").read_text()
        rendered = build_theme.render_dms_theme(self.preset, template)
        theme = json.loads(rendered)
        tokens = self.preset["tokens"]
        self.assertEqual(theme["name"], self.preset["name"])
        self.assertEqual(theme["primary"], tokens["accents"]["primary"])
        self.assertEqual(theme["surfaceText"], tokens["text"]["primary"])
        self.assertEqual(theme["outlineVariant"], tokens["borders"]["subtle"])
        self.assertEqual(theme["error"], tokens["semantic"]["error"])
        self.assertNotIn("@@", rendered)

    def test_checked_in_dms_theme_matches_contract(self):
        template = (ROOT / "themes/templates/dms-theme.json.tmpl").read_text()
        expected = build_theme.render_dms_theme(self.preset, template)
        self.assertEqual((ROOT / "dms/themes/graphite-blue/theme.json").read_text(), expected)

    def test_checked_in_generated_module_matches_preset(self):
        self.assertEqual(
            (ROOT / "hypr/.config/hypr/modules/theme_tokens.lua").read_text(),
            build_theme.render_theme(self.preset, self.template),
        )


if __name__ == "__main__":
    unittest.main()
