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
