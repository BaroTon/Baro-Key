import os
import tempfile
import unittest

from baro import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.temp.name

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self.old_home
        self.temp.cleanup()

    def test_defaults(self):
        self.assertEqual(config.load(), config.DEFAULTS)

    def test_round_trip(self):
        data = dict(config.DEFAULTS)
        data.update(
            method="vni",
            tone_style="old",
            start_enabled=False,
            free_marking=False,
            auto_restore=False,
            allow_fjzw=False,
            macros_enabled=True,
        )
        config.save(data)
        self.assertEqual(config.load(), data)

    def test_ui_style_round_trip_and_fallback(self):
        self.assertEqual(config.load()["ui_style"], "default")
        data = dict(config.DEFAULTS, ui_style="tahoe")
        config.save(data)
        self.assertEqual(config.load()["ui_style"], "tahoe")
        data["ui_style"] = "bogus"
        config.save(data)
        self.assertEqual(config.load()["ui_style"], "default")

    def test_free_shortcut_validation(self):
        for good in (
            "ctrl+shift+v", "ctrl+alt+k", "super+space", "f9", "shift+f9",
            "ctrl+f12", "alt+grave", "ctrl+shift+1", "ctrl+page_up",
            "CTRL+Shift+V",
        ):
            self.assertTrue(config.valid_shortcut(good), good)
        for bad in (
            "a", "shift+a", "shift+1", "ctrl", "ctrl+control_l", "ctrl+ctrl+a",
            "", "ctrl+", "hyper+a", "ctrl+a b", "f40", "shift+tab", None, 5,
        ):
            self.assertFalse(config.valid_shortcut(bad), bad)

    def test_modifier_only_shortcuts(self):
        for good in ("alt+shift", "shift+alt", "ctrl+shift", "ctrl+alt", "ctrl+alt+shift"):
            self.assertTrue(config.valid_shortcut(good), good)
        for bad in ("alt", "shift", "super", "ctrl", "alt+alt", ""):
            self.assertFalse(config.valid_shortcut(bad), bad)
        self.assertEqual(config.normalize_shortcut("shift+alt"), "alt+shift")

    def test_modifier_only_shortcut_round_trip(self):
        config.save(dict(config.DEFAULTS, shortcut_toggle="alt+shift"))
        self.assertEqual(config.load()["shortcut_toggle"], "alt+shift")

    def test_shortcut_is_normalized(self):
        self.assertEqual(config.normalize_shortcut("Shift+CTRL+V"), "ctrl+shift+v")
        self.assertEqual(config.normalize_shortcut("F9"), "f9")

    def test_free_shortcut_round_trip(self):
        data = dict(config.DEFAULTS, shortcut_toggle="ctrl+alt+k", shortcut_enable="f9")
        config.save(data)
        loaded = config.load()
        self.assertEqual(loaded["shortcut_toggle"], "ctrl+alt+k")
        self.assertEqual(loaded["shortcut_enable"], "f9")
        data["shortcut_toggle"] = "a"
        config.save(data)
        self.assertEqual(config.load()["shortcut_toggle"], config.DEFAULTS["shortcut_toggle"])

    def test_invalid_values_fall_back(self):
        os.makedirs(config.config_dir(), exist_ok=True)
        with open(config.config_path(), "w", encoding="utf-8") as handle:
            handle.write('{"method": "viqr", "tone_style": "weird", "free_marking": 1}')
        loaded = config.load()
        self.assertEqual(loaded["method"], config.DEFAULTS["method"])
        self.assertEqual(loaded["tone_style"], config.DEFAULTS["tone_style"])
        self.assertEqual(loaded["free_marking"], config.DEFAULTS["free_marking"])


if __name__ == "__main__":
    unittest.main()
