"""BaroKey configuration stored as JSON."""

from __future__ import annotations

import json
import os
import re

DEFAULTS = {
    "method": "telex",
    "tone_style": "modern",
    "start_enabled": True,
    "english_mode": False,
    "free_marking": True,
    "auto_restore": True,
    "allow_fjzw": True,
    "spell_check": False,
    "auto_capitalize": False,
    "clipboard_send": False,
    "standard_send": False,
    "layout_us_only": True,
    "suggest_fix_1": True,
    "suggest_fix_2": False,
    "macros_enabled": False,
    "macros_when_disabled": False,
    "theme": "dark",
    "ui_style": "default",
    "notifications": True,
    "shortcut_toggle": "ctrl+shift+v",
    "shortcut_enable": "ctrl+shift+b",
}

BOOL_KEYS = (
    "start_enabled",
    "english_mode",
    "free_marking",
    "auto_restore",
    "allow_fjzw",
    "spell_check",
    "auto_capitalize",
    "clipboard_send",
    "standard_send",
    "layout_us_only",
    "suggest_fix_1",
    "suggest_fix_2",
    "macros_enabled",
    "macros_when_disabled",
    "notifications",
)

THEMES = {"auto", "light", "dark"}
UI_STYLES = {"default", "tahoe"}

_SHORTCUT_MODIFIERS = ("ctrl", "alt", "shift", "super")
_SHORTCUT_KEY_RE = re.compile(r"^[a-z0-9_]+$")
_FUNCTION_KEY_RE = re.compile(r"^f([1-9]|[12][0-9]|3[0-5])$")
# Keys that are modifiers themselves cannot end a combination.
_MODIFIER_KEY_NAMES = {
    "control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r",
    "super_l", "super_r", "meta_l", "meta_r", "hyper_l", "hyper_r",
    "caps_lock", "num_lock", "iso_level3_shift", "iso_level5_shift",
}


def parse_shortcut_spec(spec: object):
    """Split "ctrl+alt+k" into ({"ctrl", "alt"}, "k"), or None if invalid.

    Any key may be used, as long as it cannot be mistaken for typing: it needs
    Ctrl, Alt or Super held down, except the function keys F1-F35 which may be
    used alone or with Shift.

    A combination of two or more modifiers alone ("alt+shift", as in EVKey) is
    also valid and gives ({"alt", "shift"}, None): it fires when the modifiers
    are released without another key having been pressed.
    """
    if not isinstance(spec, str):
        return None
    parts = spec.strip().lower().split("+")
    if all(part in _SHORTCUT_MODIFIERS for part in parts):
        if len(parts) >= 2 and len(set(parts)) == len(parts):
            return set(parts), None
        return None
    key = parts[-1]
    mods = parts[:-1]
    if len(set(mods)) != len(mods) or not set(mods) <= set(_SHORTCUT_MODIFIERS):
        return None
    if not _SHORTCUT_KEY_RE.match(key) or key in _MODIFIER_KEY_NAMES:
        return None
    if not _FUNCTION_KEY_RE.match(key) and not set(mods) & {"ctrl", "alt", "super"}:
        return None
    return set(mods), key


def normalize_shortcut(spec: str) -> str:
    """Canonical spelling: modifiers in a fixed order, everything lowercase."""
    mods, key = parse_shortcut_spec(spec)  # type: ignore[misc]
    ordered = [m for m in _SHORTCUT_MODIFIERS if m in mods]
    return "+".join(ordered + ([key] if key else []))


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "baro")


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


def valid_shortcut(spec: object) -> bool:
    return parse_shortcut_spec(spec) is not None


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as handle:
            saved = json.load(handle)
    except (OSError, ValueError):
        return data
    if isinstance(saved, dict):
        if saved.get("method") in {"telex", "vni"}:
            data["method"] = saved["method"]
        if saved.get("tone_style") in {"modern", "old"}:
            data["tone_style"] = saved["tone_style"]
        if saved.get("theme") in THEMES:
            data["theme"] = saved["theme"]
        if saved.get("ui_style") in UI_STYLES:
            data["ui_style"] = saved["ui_style"]
        for key in BOOL_KEYS:
            if isinstance(saved.get(key), bool):
                data[key] = saved[key]
        for key in ("shortcut_toggle", "shortcut_enable"):
            if valid_shortcut(saved.get(key)):
                data[key] = saved[key].lower()
    return data


def save(data: dict) -> None:
    os.makedirs(config_dir(), exist_ok=True)
    clean = {
        "method": data.get("method", DEFAULTS["method"]),
        "tone_style": data.get("tone_style", DEFAULTS["tone_style"]),
        "theme": data.get("theme", DEFAULTS["theme"]),
        "ui_style": data.get("ui_style", DEFAULTS["ui_style"]),
        "shortcut_toggle": data.get(
            "shortcut_toggle", DEFAULTS["shortcut_toggle"]
        ).lower(),
        "shortcut_enable": data.get(
            "shortcut_enable", DEFAULTS["shortcut_enable"]
        ).lower(),
    }
    if clean["method"] not in {"telex", "vni"}:
        clean["method"] = DEFAULTS["method"]
    if clean["tone_style"] not in {"modern", "old"}:
        clean["tone_style"] = DEFAULTS["tone_style"]
    if clean["theme"] not in THEMES:
        clean["theme"] = DEFAULTS["theme"]
    if clean["ui_style"] not in UI_STYLES:
        clean["ui_style"] = DEFAULTS["ui_style"]
    for key in ("shortcut_toggle", "shortcut_enable"):
        if not valid_shortcut(clean[key]):
            clean[key] = DEFAULTS[key]
    for key in BOOL_KEYS:
        clean[key] = bool(data.get(key, DEFAULTS[key]))

    # Keep unknown keys written by older/newer builds instead of dropping them.
    existing = {}
    try:
        with open(config_path(), "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            existing = loaded
    except (OSError, ValueError):
        pass
    existing.update(clean)

    tmp = config_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, config_path())
