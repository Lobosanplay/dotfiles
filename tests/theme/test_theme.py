import importlib.util
import json
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

    def test_checked_in_generated_module_matches_preset(self):
        self.assertEqual(
            (ROOT / "hypr/.config/hypr/modules/theme_tokens.lua").read_text(),
            build_theme.render_theme(self.preset, self.template),
        )


if __name__ == "__main__":
    unittest.main()
