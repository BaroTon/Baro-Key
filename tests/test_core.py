import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from baro.core import convert, valid_prefix  # noqa: E402


class TelexTests(unittest.TestCase):
    def check(self, raw, expected, style="modern"):
        self.assertEqual(convert(raw, "telex", style), expected)

    def test_basic_tones(self):
        self.check("as", "á")
        self.check("af", "à")
        self.check("ar", "ả")
        self.check("ax", "ã")
        self.check("aj", "ạ")

    def test_modified_vowels(self):
        self.check("aa", "â")
        self.check("aw", "ă")
        self.check("ee", "ê")
        self.check("oo", "ô")
        self.check("ow", "ơ")
        self.check("uw", "ư")
        self.check("dd", "đ")
        self.check("w", "ư")

    def test_double_tone_key_restores_letter(self):
        self.check("ass", "as")
        self.check("aff", "af")
        self.check("arr", "ar")
        self.check("axx", "ax")
        self.check("ajj", "aj")
        self.check("barr", "bar")
        self.check("barro", "baro")
        self.check("ASS", "AS")
        self.check("Barr", "Bar")
        self.check("baro", "bảo")

    def test_words(self):
        self.check("vieetj", "việt")
        self.check("tieengs", "tiếng")
        self.check("nguyeenx", "nguyễn")
        self.check("dduowcj", "được")
        self.check("thuowng", "thương")
        self.check("truowngf", "trường")
        self.check("uowcs", "ước")
        self.check("nghieeng", "nghiêng")
        self.check("quas", "quá")
        self.check("gias", "giá")
        self.check("gif", "gì")
        self.check("giuwx", "giữ")
        self.check("giuowngf", "giường")

    def test_tone_style(self):
        self.check("hoas", "hoá", "modern")
        self.check("hoas", "hóa", "old")
        self.check("thuyr", "thuỷ", "modern")
        self.check("thuyr", "thủy", "old")

    def test_invalid_restores_raw(self):
        self.check("asd", "asd")
        self.check("aaa", "aaa")
        self.check("hello", "hello")
        self.check("xyzq", "xyzq")

    def test_invalid_without_auto_restore(self):
        self.assertEqual(convert("asd", "telex", auto_restore=False), "ád")
        self.assertEqual(convert("hello", "telex", auto_restore=False), "hello")

    def test_case(self):
        self.check("AS", "Á")
        self.check("Dduowcj", "Được")
        self.check("DDUOWCJ", "ĐƯỢC")

    def test_backspace_like_prefixes(self):
        self.assertEqual(convert("n", "telex"), "n")
        self.assertEqual(convert("ng", "telex"), "ng")
        self.assertEqual(convert("ngh", "telex"), "ngh")
        self.assertEqual(convert("vi", "telex"), "vi")


class VniTests(unittest.TestCase):
    def check(self, raw, expected, style="modern"):
        self.assertEqual(convert(raw, "vni", style), expected)

    def test_tones(self):
        self.check("a1", "á")
        self.check("a2", "à")
        self.check("a3", "ả")
        self.check("a4", "ã")
        self.check("a5", "ạ")

    def test_modifiers(self):
        self.check("a6", "â")
        self.check("e6", "ê")
        self.check("o6", "ô")
        self.check("o7", "ơ")
        self.check("u7", "ư")
        self.check("a8", "ă")
        self.check("d9", "đ")

    def test_words(self):
        self.check("vie6t5", "việt")
        self.check("tie6ng1", "tiếng")
        self.check("nguye6n4", "nguyễn")
        self.check("d9uo7c5", "được")
        self.check("thuong7", "thương")
        self.check("truong7f", "truong7f")
        self.check("truong72", "trường")

    def test_invalid_restores_raw(self):
        self.check("a1b2", "a1b2")


class PrefixTests(unittest.TestCase):
    def test_valid(self):
        for word in ["a", "ng", "ngh", "qu", "gi", "đ", "ươ", "uyê", "oai", "uya"]:
            self.assertTrue(valid_prefix(word), word)

    def test_invalid(self):
        for word in ["ad", "âa", "qq", "ddx", "zz"]:
            self.assertFalse(valid_prefix(word), word)


if __name__ == "__main__":
    unittest.main()
