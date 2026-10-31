"""Tests for the bamboo-core FFI used by the IBus engine."""

from __future__ import annotations

import unittest

from baro import bamboo


def type_word(engine, keys):
    for key in keys:
        engine.process_key(key)
    return engine.preedit()


@unittest.skipUnless(bamboo.available(), bamboo.load_error() or "bamboo core not built")
class BambooEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = bamboo.BambooEngine("telex", True, True, True)

    def tearDown(self):
        self.engine.close()

    def check(self, keys, expected):
        self.engine.reset()
        self.assertEqual(type_word(self.engine, keys), expected)

    def test_basic_words(self):
        self.check("vieejt", "việt")
        self.check("tieengs", "tiếng")
        self.check("nguyeenx", "nguyễn")
        self.check("dduowcj", "được")

    def test_w_modifies_the_vowel(self):
        self.check("anw", "ăn")
        self.check("comw", "cơm")
        self.check("chuaw", "chưa")
        self.check("hoacwj", "hoặc")
        self.check("moiws", "mới")
        self.check("uow", "uơ")
        self.check("uwon", "ươn")
        self.check("huwo", "hưo")
        self.check("vuonw", "vươn")

    def test_double_key_undo(self):
        self.check("barr", "bar")
        self.check("barro", "baro")
        self.check("ass", "as")
        self.check("aww", "aw")
        self.check("ww", "w")
        self.check("ddoww", "đow")
        self.check("wwork", "work")

    def test_invalid_words_restore_raw_keys(self):
        self.check("stress", "stress")
        self.check("jazz", "jazz")
        self.check("asd", "asd")

    def test_auto_restore_can_be_disabled(self):
        engine = bamboo.BambooEngine("telex", True, True, False)
        try:
            self.assertEqual(type_word(engine, "asd"), "ád")
        finally:
            engine.close()

    def test_case_is_preserved(self):
        self.check("chEe", "chÊ")
        self.check("CHAOf", "CHÀO")
        self.check("DDaay", "Đây")

    def test_backspace_removes_output_grapheme(self):
        self.engine.reset()
        type_word(self.engine, "vieejt")
        self.assertTrue(self.engine.backspace())
        self.assertEqual(self.engine.preedit(), "vịê")
        self.engine.reset()
        self.assertFalse(self.engine.backspace())

    def test_vni(self):
        engine = bamboo.BambooEngine("vni", True, True, True)
        try:
            self.assertEqual(type_word(engine, "vie6t5"), "việt")
            engine.reset()
            self.assertEqual(type_word(engine, "d9"), "đ")
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
