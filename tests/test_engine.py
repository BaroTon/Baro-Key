"""Key-event tests for BaroEngine without a running IBus daemon."""

from __future__ import annotations

import unittest

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from baro import bamboo  # noqa: E402
from baro import core  # noqa: E402
from baro.engine import MODE_PROP_KEY, BaroEngine, make_mode_property  # noqa: E402


class FakeEngine(BaroEngine):
    def __init__(self, method="telex", tone_style="modern"):
        self.config = {
            "method": method,
            "tone_style": tone_style,
            "start_enabled": True,
        }
        self._config_mtime = 0.0
        self.buffer = ""
        self._enabled = True
        self.vietnamese = True
        self.purpose = IBus.InputPurpose.FREE_FORM
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


class ModePropertyTest(unittest.TestCase):
    def test_property_uses_input_mode_key_and_symbol(self):
        for active, text in ((True, "VI"), (False, "EN")):
            prop = make_mode_property(active)
            self.assertEqual(prop.get_key(), MODE_PROP_KEY)
            self.assertEqual(MODE_PROP_KEY, "InputMode")
            self.assertEqual(prop.get_symbol().get_text(), text)
            self.assertEqual(prop.get_label().get_text(), text)

    def test_toggle_updates_symbol_sent_to_the_panel(self):
        engine = FakeEngine()
        engine._mode_prop = make_mode_property(True)
        sent = []
        engine.update_property = lambda prop: sent.append(prop.get_symbol().get_text())
        engine._update_mode_property()
        engine.vietnamese = False
        engine._update_mode_property()
        engine._enabled = False
        engine.vietnamese = True
        engine._update_mode_property()
        self.assertEqual(sent, ["VI", "EN", "EN"])

    def test_both_keys_toggle_the_mode(self):
        for key in ("InputMode", "baro-mode"):
            engine = FakeEngine()
            engine._toggle = lambda: setattr(engine, "toggled", True)
            engine.do_property_activate(key, 0)
            self.assertTrue(getattr(engine, "toggled", False), key)


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

    def test_auto_restore_can_be_disabled(self):
        engine = FakeEngine()
        engine.config["auto_restore"] = False
        engine.type_text("asd")
        self.assertEqual(engine.preedit, "ád")

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

    def test_password_field_passes_keys_through(self):
        for purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN):
            engine = FakeEngine()
            engine.do_set_content_type(purpose, 0)
            self.assertFalse(engine.press("a"))
            self.assertFalse(engine.press("a"))
            self.assertEqual(engine.preedit, "")
            self.assertEqual(engine.committed, [])

    def test_vni_d9_makes_d_stroke(self):
        engine = FakeEngine(method="vni")
        engine.type_text("D9")
        self.assertEqual(engine.preedit, "Đ")

    def test_vni_digit_outside_word_passes_through(self):
        engine = FakeEngine(method="vni")
        handled = engine.press("1")
        self.assertFalse(handled)
        self.assertEqual(engine.buffer, "")
        self.assertEqual(engine.committed, [])

    @unittest.skipUnless(bamboo.available(), bamboo.load_error() or "bamboo core not built")
    def test_bamboo_core_used_for_preedit_and_commit(self):
        engine = FakeEngine()
        engine._bamboo = bamboo.BambooEngine("telex", True, True, True)
        engine._engine_options = engine._desired_options()
        try:
            engine.type_text("vieejt")
            self.assertEqual(engine.preedit, "việt")
            self.assertFalse(engine.press(" "))
            self.assertEqual(engine.committed, ["việt"])
            self.assertEqual(engine.preedit, "")

            engine.type_text("baro")
            self.assertEqual(engine.preedit, "bảo")
            engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
            self.assertEqual(engine.preedit, "")
        finally:
            engine._bamboo.close()
            engine._bamboo = None

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
