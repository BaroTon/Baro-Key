"""IBus engine for BARO."""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from . import core  # noqa: E402
from .config import config_path, load  # noqa: E402

ENGINE_NAME = "baro"
BUS_NAME = "org.freedesktop.IBus.Baro"

BOUNDARY_KEYS = {
    IBus.KEY_space,
    IBus.KEY_Return,
    IBus.KEY_KP_Enter,
    IBus.KEY_Tab,
    IBus.KEY_ISO_Left_Tab,
    IBus.KEY_Home,
    IBus.KEY_End,
    IBus.KEY_Page_Up,
    IBus.KEY_Page_Down,
    IBus.KEY_Up,
    IBus.KEY_Down,
    IBus.KEY_Left,
    IBus.KEY_Right,
}

MODIFIER_KEYS = {
    IBus.KEY_Shift_L,
    IBus.KEY_Shift_R,
    IBus.KEY_Control_L,
    IBus.KEY_Control_R,
    IBus.KEY_Alt_L,
    IBus.KEY_Alt_R,
    IBus.KEY_Meta_L,
    IBus.KEY_Meta_R,
    IBus.KEY_Super_L,
    IBus.KEY_Super_R,
    IBus.KEY_Caps_Lock,
    IBus.KEY_Num_Lock,
    IBus.KEY_ISO_Level3_Shift,
}


class BaroEngine(IBus.Engine):
    def __init__(self, bus, object_path):
        kwargs = {
            "connection": bus.get_connection(),
            "object_path": object_path,
        }
        if hasattr(IBus.Engine.props, "has_focus_id"):
            kwargs["has_focus_id"] = True
        super().__init__(**kwargs)
        self.config = load()
        self._config_mtime = self._mtime()
        self.buffer = ""
        self.vietnamese = bool(self.config.get("start_enabled", True))
        self.purpose = IBus.InputPurpose.FREE_FORM
        self._props = IBus.PropList()
        self._mode_prop = IBus.Property(
            key="baro-mode",
            prop_type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("VI" if self.vietnamese else "EN"),
            icon="",
            tooltip=IBus.Text.new_from_string("BARO: Tiếng Việt / English"),
            sensitive=True,
            visible=True,
            state=IBus.PropState.CHECKED if self.vietnamese else IBus.PropState.UNCHECKED,
        )
        self._props.append(self._mode_prop)
        try:
            self.register_properties(self._props)
        except Exception:
            self._props = IBus.PropList()
            self._mode_prop = None

    def _is_password(self) -> bool:
        return self.purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN)

    def _mtime(self) -> float:
        try:
            return os.stat(config_path()).st_mtime
        except OSError:
            return 0.0

    def _reload_config(self, force: bool = False) -> None:
        mtime = self._mtime()
        if force or mtime != self._config_mtime:
            self.config = load()
            self._config_mtime = mtime

    def _update_mode_property(self) -> None:
        if self._mode_prop is None:
            return
        try:
            self._mode_prop.set_label(
                IBus.Text.new_from_string("VI" if self.vietnamese else "EN")
            )
            self._mode_prop.set_state(
                IBus.PropState.CHECKED if self.vietnamese else IBus.PropState.UNCHECKED
            )
            self.update_property(self._mode_prop)
        except Exception:
            pass

    def _display(self) -> str:
        if not self.buffer:
            return ""
        return core.convert(
            self.buffer,
            self.config.get("method", "telex"),
            self.config.get("tone_style", "modern"),
        )

    def _show_preedit(self) -> None:
        if not self.buffer:
            self.hide_preedit_text()
            return
        text = self._display()
        self.update_preedit_text(IBus.Text.new_from_string(text), len(text), True)

    def _flush(self) -> None:
        if self.buffer:
            text = self._display()
            self.commit_text(IBus.Text.new_from_string(text))
            self.buffer = ""
        self.hide_preedit_text()

    def _toggle(self) -> None:
        self._flush()
        self.vietnamese = not self.vietnamese
        self._update_mode_property()

    def do_set_content_type(self, purpose, hints):
        self.purpose = purpose
        if self._is_password():
            self.buffer = ""
            self.hide_preedit_text()

    def do_enable(self):
        self._reload_config(force=True)
        self.buffer = ""
        self.vietnamese = bool(self.config.get("start_enabled", True))
        self._update_mode_property()

    def do_disable(self):
        self.buffer = ""
        self.hide_preedit_text()

    def do_focus_in(self):
        self._reload_config()

    def do_focus_out(self):
        self._flush()

    def do_reset(self):
        self.buffer = ""
        self.hide_preedit_text()

    def do_property_activate(self, prop_name, state):
        if prop_name == "baro-mode":
            self._toggle()
        return True

    def do_process_key_event(self, keyval, keycode, state):
        if self._is_password():
            self.buffer = ""
            self.hide_preedit_text()
            return False

        if state & IBus.ModifierType.RELEASE_MASK:
            return False

        ctrl = bool(state & IBus.ModifierType.CONTROL_MASK)
        alt = bool(state & IBus.ModifierType.MOD1_MASK)
        super_key = bool(state & IBus.ModifierType.SUPER_MASK)

        if ctrl and not alt and not super_key and keyval == IBus.KEY_grave:
            self._toggle()
            return True

        if alt or super_key:
            self._flush()
            return False

        if keyval in MODIFIER_KEYS:
            return False

        if ctrl:
            self._flush()
            return False

        if not self.vietnamese:
            self._flush()
            return False

        if keyval == IBus.KEY_BackSpace:
            if self.buffer:
                self.buffer = self.buffer[:-1]
                self._show_preedit()
                return True
            self.hide_preedit_text()
            return False

        if keyval == IBus.KEY_Delete or keyval == IBus.KEY_Escape:
            self.buffer = ""
            self.hide_preedit_text()
            return False

        if keyval in BOUNDARY_KEYS:
            self._flush()
            return False

        value = IBus.keyval_to_unicode(keyval)
        if isinstance(value, str):
            if not value:
                self._flush()
                return False
            char = value
        else:
            if value <= 0:
                self._flush()
                return False
            char = chr(value)

        method = self.config.get("method", "telex")
        if char.isascii() and char.isalpha():
            self.buffer += char
            self._show_preedit()
            return True

        if char in "[]" and method == "telex":
            self.buffer += char
            self._show_preedit()
            return True

        if method == "vni" and char.isdigit():
            lower = self.buffer.lower()
            has_vowel = any(ch in core.VOWELS for ch in lower)
            modifies_d = char == "9" and lower.endswith("d")
            if self.buffer and (has_vowel or modifies_d):
                self.buffer += char
                self._show_preedit()
                return True
            self._flush()
            return False

        self._flush()
        return False


class BaroEngineFactory(IBus.Factory):
    def __init__(self, bus):
        super().__init__(
            connection=bus.get_connection(), object_path=IBus.PATH_FACTORY
        )
        self._bus = bus
        self._count = 0

    def do_create_engine(self, engine_name):
        if engine_name != ENGINE_NAME:
            raise ValueError(f"unknown engine: {engine_name}")
        path = f"/org/freedesktop/IBus/Engine/Baro/{self._count}"
        self._count += 1
        return BaroEngine(self._bus, path)


def main() -> None:
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("BARO: cannot connect to the IBus daemon", file=sys.stderr)
        raise SystemExit(1)
    factory = BaroEngineFactory(bus)
    bus.request_name(BUS_NAME, 0)
    IBus.main()


if __name__ == "__main__":
    main()
