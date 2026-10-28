"""BARO configuration stored as JSON."""

from __future__ import annotations

import json
import os

DEFAULTS = {
    "method": "telex",
    "tone_style": "modern",
    "start_enabled": True,
}


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "baro")


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


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
        if isinstance(saved.get("start_enabled"), bool):
            data["start_enabled"] = saved["start_enabled"]
    return data


def save(data: dict) -> None:
    os.makedirs(config_dir(), exist_ok=True)
    clean = {
        "method": data.get("method", DEFAULTS["method"]),
        "tone_style": data.get("tone_style", DEFAULTS["tone_style"]),
        "start_enabled": bool(data.get("start_enabled", DEFAULTS["start_enabled"])),
    }
    if clean["method"] not in {"telex", "vni"}:
        clean["method"] = DEFAULTS["method"]
    if clean["tone_style"] not in {"modern", "old"}:
        clean["tone_style"] = DEFAULTS["tone_style"]
    tmp = config_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(clean, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, config_path())
