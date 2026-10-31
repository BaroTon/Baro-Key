"""BARO core: Vietnamese syllable conversion (Telex / VNI).

The engine keeps the raw keystrokes of the current word and derives the
displayed Vietnamese text from them.  If the derived text is not a valid
Vietnamese syllable *prefix* the raw keystrokes are shown unchanged, which
gives the same "restore invalid word" behaviour as EVKey.
"""

from __future__ import annotations

VOWELS = set("aăâeêioôơuưy")
MODIFIED_VOWELS = set("ăâêôơư")

TELEX_TONES = {"s": 1, "f": 2, "r": 3, "x": 4, "j": 5}
VNI_TONES = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}

_TONE_TABLE = {
    "a": "aáàảãạ",
    "ă": "ăắằẳẵặ",
    "â": "âấầẩẫậ",
    "e": "eéèẻẽẹ",
    "ê": "êếềểễệ",
    "i": "iíìỉĩị",
    "o": "oóòỏõọ",
    "ô": "ôốồổỗộ",
    "ơ": "ơớờởỡợ",
    "u": "uúùủũụ",
    "ư": "ưứừửữự",
    "y": "yýỳỷỹỵ",
}

ONSETS = sorted(
    {
        "",
        "b", "c", "ch", "d", "đ", "g", "gh", "gi", "h", "k", "kh",
        "l", "m", "n", "ng", "ngh", "nh", "p", "ph", "q", "qu",
        "r", "s", "t", "th", "tr", "v", "x",
    },
    key=len,
    reverse=True,
)

NUCLEI = sorted(
    {
        "a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y",
        "ai", "ao", "au", "ay", "âu", "ây", "eo", "êu", "ia", "iê",
        "iu", "oa", "oă", "oe", "oi", "ôi", "ơi", "ua", "uâ", "uê",
        "ui", "uô", "uơ", "uy", "ưa", "ưi", "ưu", "ươ", "yê",
        "iêu", "oai", "oay", "oeo", "uây", "uôi", "uya", "uyê",
        "uyu", "ươi", "ươu", "yêu",
    },
    key=len,
    reverse=True,
)

CODAS = sorted({"", "c", "ch", "m", "n", "ng", "nh", "p", "t"}, key=len, reverse=True)


def _with_tone(ch: str, tone: int) -> str:
    table = _TONE_TABLE.get(ch)
    if table is None:
        return ch
    return table[tone]


def _valid_rest(rest: str) -> bool:
    if not rest:
        return True
    for nucleus in NUCLEI:
        for coda in CODAS:
            if (nucleus + coda).startswith(rest):
                return True
    return False


def valid_prefix(word: str) -> bool:
    """True if *word* (base letters, no tone) can start a Vietnamese word."""
    if not word:
        return True
    for onset in ONSETS:
        if word.startswith(onset) and _valid_rest(word[len(onset):]):
            return True
    return False


def _split_syllable(word: str):
    """Return (onset, nucleus, coda) for a complete base word, or None."""
    for onset in ONSETS:
        if not word.startswith(onset):
            continue
        rest = word[len(onset):]
        if not rest or not any(ch in VOWELS for ch in rest):
            continue
        for nucleus in NUCLEI:
            if not rest.startswith(nucleus):
                continue
            coda = rest[len(nucleus):]
            if coda in CODAS:
                return onset, nucleus, coda
    return None


def _tone_index(nucleus: str, coda: str, style: str) -> int:
    modified = [i for i, ch in enumerate(nucleus) if ch in MODIFIED_VOWELS]
    if modified:
        return modified[-1]
    if coda:
        return len(nucleus) - 1
    if len(nucleus) == 1:
        return 0
    if len(nucleus) >= 3:
        return 1
    if style == "modern" and nucleus in {"oa", "oe", "uy"}:
        return 1
    return 0


def _parse_telex(raw: str):
    letters: list[str] = []
    tone = 0
    literal = False
    for ch in raw:
        has_vowel = any(c in VOWELS for c in letters)
        if ch in TELEX_TONES and has_vowel:
            new_tone = TELEX_TONES[ch]
            if tone == new_tone:
                # Gõ lặp phím dấu để lấy chính ký tự đó: "ass" -> "as".
                letters.append(ch)
                tone = 0
                literal = True
            else:
                tone = new_tone
            continue
        if ch == "z" and has_vowel:
            if tone:
                tone = 0
                continue
            letters.append("z")
            continue
        if ch == "w":
            if len(letters) >= 2 and letters[-2] == "u" and letters[-1] == "o":
                letters[-2:] = ["ư", "ơ"]
                continue
            if letters and letters[-1] == "a":
                letters[-1] = "ă"
                continue
            if letters and letters[-1] == "o":
                letters[-1] = "ơ"
                continue
            if letters and letters[-1] == "u":
                letters[-1] = "ư"
                continue
            letters.append("ư")
            continue
        if ch in "aeo" and letters and letters[-1] == ch:
            letters[-1] = {"a": "â", "e": "ê", "o": "ô"}[ch]
            continue
        if ch == "d" and letters and letters[-1] == "d":
            letters[-1] = "đ"
            continue
        if ch == "[":
            letters.append("ơ")
            continue
        if ch == "]":
            letters.append("ư")
            continue
        letters.append(ch)
    return "".join(letters), tone, literal


def _parse_vni(raw: str):
    letters: list[str] = []
    tone = 0
    for ch in raw:
        has_vowel = any(c in VOWELS for c in letters)
        if ch in VNI_TONES and has_vowel:
            new_tone = VNI_TONES[ch]
            tone = 0 if tone == new_tone else new_tone
            continue
        if ch == "0" and has_vowel:
            if tone:
                tone = 0
                continue
            letters.append("0")
            continue
        if ch in "6789":
            if ch == "6":
                for i in range(len(letters) - 1, -1, -1):
                    if letters[i] in "aeo":
                        letters[i] = {"a": "â", "e": "ê", "o": "ô"}[letters[i]]
                        break
                else:
                    letters.append("6")
            elif ch == "7":
                text = "".join(letters)
                pos = text.rfind("uo")
                if pos != -1:
                    letters[pos:pos + 2] = ["ư", "ơ"]
                else:
                    for i in range(len(letters) - 1, -1, -1):
                        if letters[i] in "ou":
                            letters[i] = {"o": "ơ", "u": "ư"}[letters[i]]
                            break
                    else:
                        letters.append("7")
            elif ch == "8":
                for i in range(len(letters) - 1, -1, -1):
                    if letters[i] == "a":
                        letters[i] = "ă"
                        break
                else:
                    letters.append("8")
            elif ch == "9":
                for i in range(len(letters) - 1, -1, -1):
                    if letters[i] == "d":
                        letters[i] = "đ"
                        break
                else:
                    letters.append("9")
            continue
        letters.append(ch)
    return "".join(letters), tone


def _match_case(text: str, raw: str) -> str:
    if not text:
        return text
    if raw.isupper():
        return text.upper()
    if raw[0].isupper():
        return text[0].upper() + text[1:]
    return text


def convert(
    raw: str,
    method: str = "telex",
    style: str = "modern",
    auto_restore: bool = True,
) -> str:
    """Convert raw keystrokes into Vietnamese, restoring raw when invalid."""
    if not raw:
        return ""
    lowered = raw.lower()
    if method == "vni":
        letters, tone = _parse_vni(lowered)
        literal = False
    else:
        letters, tone, literal = _parse_telex(lowered)

    if not valid_prefix(letters) and auto_restore and not literal:
        return raw

    if tone:
        split = _split_syllable(letters)
        if split is not None:
            onset, nucleus, coda = split
            index = len(onset) + _tone_index(nucleus, coda, style)
            if 0 <= index < len(letters) and letters[index] in VOWELS:
                letters = letters[:index] + _with_tone(letters[index], tone) + letters[index + 1:]
        else:
            for i in range(len(letters) - 1, -1, -1):
                if letters[i] in VOWELS:
                    letters = letters[:i] + _with_tone(letters[i], tone) + letters[i + 1:]
                    break

    return _match_case(letters, raw)


def is_word_char(char: str, method: str) -> bool:
    if char.isascii() and char.isalpha():
        return True
    if char in "[]":
        return True
    if method == "vni" and char.isdigit():
        return True
    return False
