"""Key-event tests for BaroEngine without a running IBus daemon."""

from __future__ import annotations

import unittest

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from baro import bamboo  # noqa: E402
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


class ShortcutMatchTest(unittest.TestCase):
    CTRL = int(IBus.ModifierType.CONTROL_MASK)
    SHIFT = int(IBus.ModifierType.SHIFT_MASK)
    ALT = int(IBus.ModifierType.MOD1_MASK)
    SUPER = int(IBus.ModifierType.SUPER_MASK)

    def matches(self, spec, keyval, state):
        return FakeEngine()._matches_shortcut(keyval, state, spec)

    def test_letter_combinations(self):
        self.assertTrue(self.matches("ctrl+alt+k", IBus.KEY_k, self.CTRL | self.ALT))
        self.assertFalse(self.matches("ctrl+alt+k", IBus.KEY_k, self.CTRL))
        self.assertFalse(self.matches("ctrl+alt+k", IBus.KEY_j, self.CTRL | self.ALT))

    def test_shifted_letter_arrives_upper_case(self):
        self.assertTrue(
            self.matches("ctrl+shift+v", IBus.KEY_V, self.CTRL | self.SHIFT)
        )

    def test_function_keys_work_alone(self):
        self.assertTrue(self.matches("f9", IBus.KEY_F9, 0))
        self.assertFalse(self.matches("f9", IBus.KEY_F9, self.CTRL))
        self.assertTrue(self.matches("shift+f9", IBus.KEY_F9, self.SHIFT))

    def test_named_keys(self):
        self.assertTrue(self.matches("super+space", IBus.KEY_space, self.SUPER))
        self.assertTrue(self.matches("ctrl+page_up", IBus.KEY_Page_Up, self.CTRL))
        self.assertTrue(self.matches("alt+grave", IBus.KEY_grave, self.ALT))
        self.assertTrue(self.matches("ctrl+backspace", IBus.KEY_BackSpace, self.CTRL))

    def test_shifted_symbols_match_their_base_key(self):
        self.assertTrue(
            self.matches("ctrl+shift+1", IBus.KEY_exclam, self.CTRL | self.SHIFT)
        )
        self.assertTrue(
            self.matches("ctrl+shift+slash", IBus.KEY_question, self.CTRL | self.SHIFT)
        )

    def test_invalid_specs_never_match(self):
        for spec in ("a", "shift+a", "ctrl+nosuchkey", "", "ctrl"):
            self.assertFalse(self.matches(spec, IBus.KEY_a, self.CTRL), spec)

    def test_custom_shortcut_toggles_the_mode(self):
        engine = FakeEngine()
        engine.config["shortcut_toggle"] = "ctrl+alt+k"
        toggled = []
        engine._toggle = lambda: toggled.append(True)
        self.assertTrue(
            engine.do_process_key_event(IBus.KEY_k, 0, self.CTRL | self.ALT)
        )
        self.assertEqual(toggled, [True])


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
