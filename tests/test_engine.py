"""Key-event tests for BaroEngine without a running IBus daemon."""

from __future__ import annotations

import os
import tempfile
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
        self.preedit_attrs = None
        self.committed = []

    def _reload_config(self, force=False):
        pass

    def hide_preedit_text(self):
        self.preedit = ""
        self.preedit_visible = False

    def update_preedit_text(self, text, cursor, visible):
        self.preedit = text.get_text()
        self.preedit_attrs = text.get_attributes()
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


class ModifierChordTest(unittest.TestCase):
    """Modifier-only shortcuts such as alt+shift, which fire on release."""

    ALT = int(IBus.ModifierType.MOD1_MASK)
    SHIFT = int(IBus.ModifierType.SHIFT_MASK)
    CTRL = int(IBus.ModifierType.CONTROL_MASK)
    REL = int(IBus.ModifierType.RELEASE_MASK)

    def make(self, toggle="alt+shift", enable="ctrl+alt"):
        engine = FakeEngine()
        engine.config["shortcut_toggle"] = toggle
        engine.config["shortcut_enable"] = enable
        engine.calls = []
        engine._toggle = lambda: engine.calls.append("toggle")
        engine._toggle_enabled = lambda: engine.calls.append("enable")
        return engine

    def test_alt_shift_fires_once_on_release(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.ALT)
        self.assertEqual(engine.calls, [], "nothing fires while keys are down")
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.ALT | self.SHIFT)
        self.assertEqual(engine.calls, ["toggle"])
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.REL | self.ALT)
        self.assertEqual(engine.calls, ["toggle"], "second release must not fire again")

    def test_order_of_pressing_does_not_matter(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Shift_R, 0, 0)
        engine.do_process_key_event(IBus.KEY_Alt_R, 0, self.SHIFT)
        engine.do_process_key_event(IBus.KEY_Shift_R, 0, self.REL | self.SHIFT | self.ALT)
        engine.do_process_key_event(IBus.KEY_Alt_R, 0, self.REL | self.ALT)
        self.assertEqual(engine.calls, ["toggle"])

    def test_another_key_in_between_cancels_it(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.ALT)
        engine.do_process_key_event(IBus.KEY_Tab, 0, self.ALT | self.SHIFT)
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.ALT | self.SHIFT)
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.REL | self.ALT)
        self.assertEqual(engine.calls, [])

    def test_a_single_modifier_does_nothing(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.REL | self.ALT)
        self.assertEqual(engine.calls, [])

    def test_extra_modifier_is_a_different_chord(self):
        engine = self.make()
        for keyval, state in (
            (IBus.KEY_Control_L, 0),
            (IBus.KEY_Alt_L, self.CTRL),
            (IBus.KEY_Shift_L, self.CTRL | self.ALT),
        ):
            engine.do_process_key_event(keyval, 0, state)
        for keyval in (IBus.KEY_Shift_L, IBus.KEY_Alt_L, IBus.KEY_Control_L):
            engine.do_process_key_event(keyval, 0, self.REL)
        self.assertEqual(engine.calls, [])

    def test_can_fire_again_after_everything_is_released(self):
        engine = self.make()
        for _ in range(2):
            engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
            engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.ALT)
            engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.ALT | self.SHIFT)
            engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.REL | self.ALT)
        self.assertEqual(engine.calls, ["toggle", "toggle"])

    def test_second_binding_uses_the_enable_action(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Control_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.CTRL)
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, self.REL | self.CTRL | self.ALT)
        engine.do_process_key_event(IBus.KEY_Control_L, 0, self.REL | self.CTRL)
        self.assertEqual(engine.calls, ["enable"])

    def test_modifier_events_are_never_consumed(self):
        engine = self.make()
        self.assertFalse(engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0))
        self.assertFalse(engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.ALT))
        self.assertFalse(
            engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.ALT | self.SHIFT)
        )

    def test_a_lost_release_does_not_leave_stale_state(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)  # its release never arrives
        engine.do_process_key_event(IBus.KEY_a, 0, 0)  # plain key: no modifier is down
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.SHIFT)
        self.assertEqual(engine.calls, [])

    def test_focus_change_forgets_held_modifiers(self):
        engine = self.make()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.ALT)
        engine._reset_chord()
        engine.do_process_key_event(IBus.KEY_Shift_L, 0, self.REL | self.ALT | self.SHIFT)
        self.assertEqual(engine.calls, [])

    def test_key_combinations_still_work_next_to_chords(self):
        engine = self.make(toggle="ctrl+alt+k")
        engine.do_process_key_event(IBus.KEY_k, 0, self.CTRL | self.ALT)
        self.assertEqual(engine.calls, ["toggle"])


class KeyDebugLogTest(unittest.TestCase):
    """The shortcut diagnostics must never record what the user types."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = self.temp.name
        self.dir = os.path.join(self.temp.name, "baro")
        self.flag = os.path.join(self.dir, "debug-keys")
        self.log = os.path.join(self.dir, "keys.log")

    def tearDown(self):
        if self.old_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self.old_cache
        self.temp.cleanup()

    def enable(self):
        os.makedirs(self.dir, exist_ok=True)
        open(self.flag, "w").close()

    def read(self):
        try:
            with open(self.log, encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return ""

    def test_nothing_is_written_without_the_flag_file(self):
        engine = FakeEngine()
        engine.do_process_key_event(IBus.KEY_Alt_L, 0, 0)
        engine.do_process_key_event(IBus.KEY_F9, 0, 0)
        self.assertFalse(os.path.exists(self.log))

    def test_modifiers_combos_and_function_keys_are_logged(self):
        self.enable()
        engine = FakeEngine()
        engine.config["shortcut_toggle"] = "ctrl+shift+v"
        engine.do_process_key_event(IBus.KEY_Alt_L, 38, 0)
        engine.do_process_key_event(IBus.KEY_Shift_L, 50, int(IBus.ModifierType.MOD1_MASK))
        engine.do_process_key_event(
            IBus.KEY_s, 39, int(IBus.ModifierType.MOD1_MASK | IBus.ModifierType.SHIFT_MASK)
        )
        engine.do_process_key_event(IBus.KEY_F9, 75, 0)
        text = self.read()
        for expected in ("Alt_L", "Shift_L", " s ", "F9", "keycode=39", "state=0x9"):
            self.assertIn(expected, text)
        self.assertIn("toggle='ctrl+shift+v'", text)

    def test_ordinary_typing_is_never_logged(self):
        self.enable()
        engine = FakeEngine()
        engine.type_text("matkhau123")
        engine.do_process_key_event(IBus.KEY_A, 0, int(IBus.ModifierType.SHIFT_MASK))
        self.assertEqual(self.read(), "", "typed text must not reach the log")

    def test_actions_are_logged(self):
        self.enable()
        engine = FakeEngine()
        engine.config["shortcut_toggle"] = "f9"
        engine._toggle_mode = lambda: None
        engine.do_process_key_event(IBus.KEY_F9, 75, 0)
        self.assertIn("ACTION  switch Vietnamese / English", self.read())


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

    def test_preedit_is_not_underlined(self):
        engine = FakeEngine()
        engine.type_text("vieejt")
        attrs = engine.preedit_attrs
        self.assertIsNotNone(attrs)
        attr = attrs.get(0)
        self.assertEqual(attr.get_attr_type(), IBus.AttrType.UNDERLINE)
        self.assertEqual(attr.get_value(), IBus.AttrUnderline.NONE)
        self.assertEqual(attr.get_start_index(), 0)
        self.assertEqual(attr.get_end_index(), len(engine.preedit))

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
