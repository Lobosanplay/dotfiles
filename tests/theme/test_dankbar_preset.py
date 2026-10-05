import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("apply_dankbar_preset", ROOT / "scripts/apply_dankbar_preset.py")
apply_dankbar_preset = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply_dankbar_preset)


class DankBarPresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dankbar-preset-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_path = self.root / "settings.json"
        self.theme_dir = self.root / "themes"
        self.original = {
            "currentThemeName": "blue",
            "customThemeFile": "",
            "showWorkspaceIndex": False,
            "workspaceScrolling": True,
            "unrelatedPreference": {"preserve": True},
            "barConfigs": [
                {
                    "id": "default",
                    "leftWidgets": ["launcherButton"],
                    "centerWidgets": ["music", "clock", "weather"],
                    "rightWidgets": ["cpuUsage", "controlCenterButton"],
                    "shadowIntensity": 3,
                    "island": True,
                }
            ],
        }
        self.settings_path.write_text(json.dumps(self.original, indent=2) + "\n")

    def test_apply_preserves_unrelated_settings_and_backs_up_original(self):
        theme_path, changed, backup_path = apply_dankbar_preset.apply(self.settings_path, self.theme_dir)
        self.assertTrue(changed)
        self.assertIsNotNone(backup_path)
        self.assertEqual(json.loads(backup_path.read_text()), self.original)

        result = json.loads(self.settings_path.read_text())
        self.assertEqual(result["unrelatedPreference"], {"preserve": True})
        self.assertEqual(result["barConfigs"][0]["shadowIntensity"], 3)
        self.assertTrue(result["barConfigs"][0]["island"])
        self.assertEqual(result["barConfigs"][0]["centerWidgets"], ["clock"])
        self.assertEqual(result["matugenScheme"], "scheme-neutral")
        self.assertEqual(result["currentThemeName"], "dynamic")
        self.assertEqual(result["currentThemeCategory"], "dynamic")
        self.assertEqual(result["barConfigs"][0]["transparency"], 0.74)
        self.assertEqual(result["barConfigs"][0]["widgetTransparency"], 0.92)
        self.assertEqual(
            [widget["id"] for widget in result["barConfigs"][0]["leftWidgets"]],
            ["launcherButton", "systemTray", "battery"],
        )
        self.assertEqual(
            [widget["id"] for widget in result["barConfigs"][0]["rightWidgets"]],
            ["cpuUsage", "memUsage", "cpuTemp", "controlCenterButton"],
        )
        widget_ids = {
            widget["id"] if isinstance(widget, dict) else widget
            for group in ("leftWidgets", "centerWidgets", "rightWidgets")
            for widget in result["barConfigs"][0][group]
        }
        self.assertNotIn("workspaceSwitcher", widget_ids)
        self.assertNotIn("notificationButton", widget_ids)
        self.assertFalse(result["barConfigs"][0]["scrollEnabled"])
        self.assertTrue(result["showWorkspaceIndex"])
        self.assertFalse(result["workspaceScrolling"])
        self.assertEqual(Path(result["customThemeFile"]), theme_path)
        self.assertEqual(theme_path.read_bytes(), apply_dankbar_preset.THEME_SOURCE.read_bytes())
        self.assertTrue(apply_dankbar_preset.check(self.settings_path, self.theme_dir))

    def test_apply_is_idempotent(self):
        apply_dankbar_preset.apply(self.settings_path, self.theme_dir)
        before = self.settings_path.read_bytes()
        theme_path, changed, backup_path = apply_dankbar_preset.apply(self.settings_path, self.theme_dir)
        self.assertFalse(changed)
        self.assertIsNone(backup_path)
        self.assertEqual(self.settings_path.read_bytes(), before)
        self.assertTrue(theme_path.is_file())

    def test_check_accepts_dms_omitting_default_settings(self):
        apply_dankbar_preset.apply(self.settings_path, self.theme_dir)
        normalized = json.loads(self.settings_path.read_text())
        for key in apply_dankbar_preset.DMS_SETTING_DEFAULTS:
            normalized.pop(key, None)
        self.settings_path.write_text(json.dumps(normalized, indent=2) + "\n")
        self.assertTrue(apply_dankbar_preset.check(self.settings_path, self.theme_dir))

    def test_apply_refuses_to_replace_an_unrelated_theme(self):
        target = self.theme_dir / apply_dankbar_preset.THEME_DIR_NAME / "theme.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}\n")
        original_bytes = self.settings_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            apply_dankbar_preset.apply(self.settings_path, self.theme_dir)
        self.assertEqual(self.settings_path.read_bytes(), original_bytes)
        self.assertFalse(self.settings_path.with_name("settings.json.before-phase20").exists())


if __name__ == "__main__":
    unittest.main()
