"""Key-event tests for BaroEngine without a running IBus daemon."""

from __future__ import annotations

import unittest

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from baro import core  # noqa: E402
from baro.engine import BaroEngine  # noqa: E402


class FakeEngine(BaroEngine):
    def __init__(self, method="telex", tone_style="modern"):
        self.config = {
            "method": method,
            "tone_style": tone_style,
            "start_enabled": True,
        }
        self._config_mtime = 0.0
        self.buffer = ""
        self.vietnamese = True
        self._mode_prop = None
        self.preedit = ""
        self.preedit_visible = False
        self.committed = []

    def _reload_config(self, force=False):
        pass

    def hide_preedit_text(self):
        self.preedit = ""
        self.preedit_visible = False

    def update_preedit_text(self, text, cursor, visible):
        self.preedit = text.get_text()
        self.preedit_visible = visible

    def commit_text(self, text):
        self.committed.append(text.get_text())

    def update_property(self, prop):
        pass

    def press(self, char, state=0):
        keyval = IBus.KEY_space if char == " " else IBus.unicode_to_keyval(char)
        return self.do_process_key_event(keyval, 0, state)

    def type_text(self, text, state=0):
        for char in text:
            self.press(char, state)


class EngineKeyEventTest(unittest.TestCase):
    def test_telex_word_committed_on_space(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        self.assertEqual(engine.preedit, "việt")
        self.assertFalse(engine.press(" "))
        self.assertEqual(engine.committed, ["việt"])
        self.assertEqual(engine.preedit, "")

    def test_vni_word_committed_on_return(self):
        engine = FakeEngine(method="vni")
        engine.type_text("vie6t5")
        self.assertEqual(engine.preedit, "việt")
        self.do_return(engine)
        self.assertEqual(engine.committed, ["việt"])

    def test_invalid_word_restores_raw_keys(self):
        engine = FakeEngine()
        engine.type_text("asd")
        self.assertEqual(engine.preedit, "asd")
        engine.press(" ")
        self.assertEqual(engine.committed, ["asd"])

    def test_backspace_updates_preedit(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        self.do_backspace(engine)
        self.assertEqual(engine.preedit, core.convert("vieej"))
        self.assertEqual(engine.buffer, "vieej")

    def test_escape_clears_without_commit(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(engine.preedit, "")
        self.assertEqual(engine.committed, [])

    def test_ctrl_grave_toggles_after_flush(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        handled = engine.do_process_key_event(
            IBus.KEY_grave, 0, IBus.ModifierType.CONTROL_MASK
        )
        self.assertTrue(handled)
        self.assertFalse(engine.vietnamese)
        self.assertEqual(engine.committed, ["việt"])

    def test_vni_digit_outside_word_passes_through(self):
        engine = FakeEngine(method="vni")
        handled = engine.press("1")
        self.assertFalse(handled)
        self.assertEqual(engine.buffer, "")
        self.assertEqual(engine.committed, [])

    def test_alt_flushes_and_passes_through(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        handled = engine.do_process_key_event(
            IBus.unicode_to_keyval("a"), 0, IBus.ModifierType.MOD1_MASK
        )
        self.assertFalse(handled)
        self.assertEqual(engine.committed, ["việt"])

    def do_return(self, engine):
        engine.do_process_key_event(IBus.KEY_Return, 0, 0)

    def do_backspace(self, engine):
        engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)


if __name__ == "__main__":
    unittest.main()
