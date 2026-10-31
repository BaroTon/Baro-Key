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

_SHORTCUT_RE = re.compile(
    r"^(?:(?:ctrl|alt|shift|super)\+)+(?:[a-z0-9]|grave|space|tab|return|"
    r"backslash|bracketleft|bracketright|semicolon|apostrophe|comma|period|"
    r"slash|minus|equal)$"
)


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "baro")


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


def valid_shortcut(spec: object) -> bool:
    return isinstance(spec, str) and bool(_SHORTCUT_RE.match(spec.lower()))


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
