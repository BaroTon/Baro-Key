"""IBus engine for BaroKey."""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from . import bamboo, core, notify  # noqa: E402
from .config import config_path, load, save  # noqa: E402

ENGINE_NAME = "baro"
BUS_NAME = "org.freedesktop.IBus.Baro"

_SHORTCUT_KEYS = {
    "grave": IBus.KEY_grave,
    "space": IBus.KEY_space,
    "tab": IBus.KEY_Tab,
    "return": IBus.KEY_Return,
    "backslash": ord("\\"),
    "bracketleft": ord("["),
    "bracketright": ord("]"),
    "semicolon": ord(";"),
    "apostrophe": ord("'"),
    "comma": ord(","),
    "period": ord("."),
    "slash": ord("/"),
    "minus": ord("-"),
    "equal": ord("="),
}


def parse_shortcut(spec: str):
    """Return (keyval, ctrl, shift, alt, super) or None for an invalid spec."""
    try:
        parts = spec.lower().replace(" ", "").split("+")
    except AttributeError:
        return None
    if len(parts) < 2:
        return None
    key = parts[-1]
    mods = set(parts[:-1])
    if not mods or not mods <= {"ctrl", "shift", "alt", "super"}:
        return None
    if key in _SHORTCUT_KEYS:
        keyval = _SHORTCUT_KEYS[key]
    elif len(key) == 1 and (key.isalpha() or key.isdigit()):
        keyval = ord(key)
    else:
        return None
    return (
        keyval,
        "ctrl" in mods,
        "shift" in mods,
        "alt" in mods,
        "super" in mods,
    )

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


# GNOME Shell shows the symbol of the property whose key is "InputMode" in the
# top bar (two characters at most), next to the input source. Using that key
# lets the bar follow the Vietnamese / English mode instead of staying on the
# static <symbol> from the component file.
MODE_PROP_KEY = "InputMode"
LEGACY_MODE_PROP_KEY = "baro-mode"


def mode_symbol(active: bool) -> str:
    return "VI" if active else "EN"


def make_mode_property(active: bool) -> "IBus.Property":
    text = mode_symbol(active)
    return IBus.Property(
        key=MODE_PROP_KEY,
        prop_type=IBus.PropType.NORMAL,
        label=IBus.Text.new_from_string(text),
        symbol=IBus.Text.new_from_string(text),
        icon="",
        tooltip=IBus.Text.new_from_string("BaroKey: Tiếng Việt / English"),
        sensitive=True,
        visible=True,
        state=IBus.PropState.CHECKED if active else IBus.PropState.UNCHECKED,
    )


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
        self._bamboo = None
        self._engine_options = None
        self._open_engine()
        self._enabled = bool(self.config.get("start_enabled", True))
        self.vietnamese = not bool(self.config.get("english_mode", False))
        self.purpose = IBus.InputPurpose.FREE_FORM
        self._props = IBus.PropList()
        self._mode_prop = make_mode_property(self._enabled and self.vietnamese)
        self._props.append(self._mode_prop)
        self._register_properties()

    def _register_properties(self) -> None:
        """(Re)send the property list so the panel can show the mode.

        Done at start and again on enable / focus-in: a registration sent
        while the daemon is still wiring up the engine is dropped, and the
        panel only follows later updates for properties it has been given.
        """
        if self._mode_prop is None:
            return
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

    def _desired_options(self):
        return (
            str(self.config.get("method", "telex")),
            str(self.config.get("tone_style", "modern")) == "modern",
            bool(self.config.get("free_marking", True)),
            bool(self.config.get("auto_restore", True)),
        )

    def _open_engine(self) -> None:
        options = self._desired_options()
        try:
            self._bamboo = bamboo.BambooEngine(*options)
        except Exception:
            # Keep BARO usable on machines where the Rust library has not been
            # built: the pure-Python core still provides Telex/VNI.
            self._bamboo = None
        self._engine_options = options

    def _sync_engine(self) -> None:
        engine = getattr(self, "_bamboo", None)
        options = self._desired_options()
        if engine is None:
            self._open_engine()
            return
        if options == getattr(self, "_engine_options", None):
            return
        try:
            engine.configure(*options)
            self._engine_options = options
        except Exception:
            engine.close()
            self._open_engine()

    def _clear_word(self) -> None:
        self.buffer = ""
        engine = getattr(self, "_bamboo", None)
        if engine is not None:
            try:
                engine.reset()
            except Exception:
                pass

    def _update_mode_property(self) -> None:
        if self._mode_prop is None:
            return
        try:
            active = self._enabled and self.vietnamese
            text = IBus.Text.new_from_string(mode_symbol(active))
            self._mode_prop.set_label(text)
            self._mode_prop.set_symbol(IBus.Text.new_from_string(mode_symbol(active)))
            self._mode_prop.set_state(
                IBus.PropState.CHECKED if active else IBus.PropState.UNCHECKED
            )
            self.update_property(self._mode_prop)
        except Exception:
            pass

    def _persist(self, **values) -> None:
        self._reload_config()
        self.config.update(values)
        try:
            save(self.config)
        except Exception:
            # A read-only config directory must not interrupt typing.
            pass
        self._config_mtime = self._mtime()

    def _send_notification(self, title: str, body: str) -> None:
        if self.config.get("notifications", True):
            notify.send(title, body)

    def _toggle_mode(self) -> None:
        self._flush()
        self._reload_config()
        if not self._enabled:
            self._enabled = True
            self.vietnamese = True
        else:
            self.vietnamese = not self.vietnamese
        self._persist(
            start_enabled=self._enabled,
            english_mode=not self.vietnamese,
        )
        self._update_mode_property()
        shortcut = notify.shortcut_label(
            self.config.get("shortcut_toggle", "ctrl+shift+v")
        )
        if self.vietnamese:
            self._send_notification(
                "Đã chuyển sang chế độ Tiếng Việt",
                f"BaroKey sẽ gõ tiếng Việt. Nhấn {shortcut} để chuyển lại.",
            )
        else:
            self._send_notification(
                "Đã chuyển sang chế độ Tiếng Anh",
                f"Nhấn {shortcut} để quay lại tiếng Việt.",
            )

    def _toggle_enabled(self) -> None:
        self._flush()
        self._reload_config()
        self._enabled = not self._enabled
        if self._enabled:
            self.vietnamese = not bool(self.config.get("english_mode", False))
        self._persist(start_enabled=self._enabled)
        self._update_mode_property()
        shortcut = notify.shortcut_label(
            self.config.get("shortcut_enable", "ctrl+shift+b")
        )
        if self._enabled:
            self._send_notification(
                "Đã bật bộ gõ tiếng Việt",
                "BaroKey đã sẵn sàng hoạt động.",
            )
        else:
            self._send_notification(
                "Đã tắt bộ gõ tiếng Việt",
                f"Nhấn {shortcut} để bật lại.",
            )

    def _matches_shortcut(self, keyval, state, spec: str) -> bool:
        parsed = parse_shortcut(spec)
        if parsed is None:
            return False
        expected, ctrl, shift, alt, super_key = parsed
        if state & IBus.ModifierType.SHIFT_MASK and ord("A") <= keyval <= ord("Z"):
            keyval += 32
        return (
            keyval == expected
            and bool(state & IBus.ModifierType.CONTROL_MASK) == ctrl
            and bool(state & IBus.ModifierType.SHIFT_MASK) == shift
            and bool(state & IBus.ModifierType.MOD1_MASK) == alt
            and bool(state & IBus.ModifierType.SUPER_MASK) == super_key
        )

    def _display(self) -> str:
        if not self.buffer:
            return ""
        engine = getattr(self, "_bamboo", None)
        if engine is not None:
            return engine.preedit()
        return core.convert(
            self.buffer,
            self.config.get("method", "telex"),
            self.config.get("tone_style", "modern"),
            self.config.get("auto_restore", True),
        )

    def _show_preedit(self) -> None:
        if not self.buffer:
            self.hide_preedit_text()
            return
        text = self._display()
        if not text:
            self.hide_preedit_text()
            return
        self.update_preedit_text(IBus.Text.new_from_string(text), len(text), True)

    def _flush(self) -> None:
        if self.buffer:
            text = self._display() or self.buffer
            self.commit_text(IBus.Text.new_from_string(text))
            self._clear_word()
        self.hide_preedit_text()

    def _toggle(self) -> None:
        self._toggle_mode()

    def do_set_content_type(self, purpose, hints):
        self.purpose = purpose
        if self._is_password():
            self._clear_word()
            self.hide_preedit_text()

    def do_enable(self):
        self._reload_config(force=True)
        self._clear_word()
        self._enabled = bool(self.config.get("start_enabled", True))
        self.vietnamese = not bool(self.config.get("english_mode", False))
        self._sync_engine()
        self._update_mode_property()
        self._register_properties()

    def do_disable(self):
        self._clear_word()
        self.hide_preedit_text()

    def do_focus_in(self):
        old_mtime = self._config_mtime
        self._reload_config()
        if self._config_mtime != old_mtime:
            self._enabled = bool(self.config.get("start_enabled", True))
            self.vietnamese = not bool(self.config.get("english_mode", False))
            self._update_mode_property()
        self._sync_engine()
        self._register_properties()

    def do_focus_out(self):
        self._flush()

    def do_reset(self):
        self._clear_word()
        self.hide_preedit_text()

    def do_property_activate(self, prop_name, state):
        if prop_name in (MODE_PROP_KEY, LEGACY_MODE_PROP_KEY):
            self._toggle()
        return True

    def _feed(self, char: str) -> bool:
        engine = getattr(self, "_bamboo", None)
        if engine is not None:
            try:
                if not engine.process_key(char):
                    self._flush()
                    return False
            except Exception:
                # A broken FFI library must not take the whole IME down.
                self._bamboo = None
        self.buffer += char
        self._show_preedit()
        return True

    def do_process_key_event(self, keyval, keycode, state):
        if self._is_password():
            self._clear_word()
            self.hide_preedit_text()
            return False

        if state & IBus.ModifierType.RELEASE_MASK:
            return False

        ctrl = bool(state & IBus.ModifierType.CONTROL_MASK)
        alt = bool(state & IBus.ModifierType.MOD1_MASK)
        super_key = bool(state & IBus.ModifierType.SUPER_MASK)

        if self._matches_shortcut(
            keyval, state, self.config.get("shortcut_enable", "ctrl+shift+b")
        ):
            self._toggle_enabled()
            return True

        if self._matches_shortcut(
            keyval, state, self.config.get("shortcut_toggle", "ctrl+shift+v")
        ) or (ctrl and not alt and not super_key and keyval == IBus.KEY_grave):
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

        if not self._enabled or not self.vietnamese:
            self._flush()
            return False

        if keyval == IBus.KEY_BackSpace:
            if self.buffer:
                engine = getattr(self, "_bamboo", None)
                if engine is not None:
                    try:
                        engine.backspace()
                    except Exception:
                        pass
                self.buffer = self.buffer[:-1]
                self._show_preedit()
                return True
            self.hide_preedit_text()
            return False

        if keyval == IBus.KEY_Delete or keyval == IBus.KEY_Escape:
            self._clear_word()
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
            return self._feed(char)

        if char in "[]" and method == "telex":
            return self._feed(char)

        if method == "vni" and char.isdigit():
            lower = self.buffer.lower()
            has_vowel = any(ch in core.VOWELS for ch in lower)
            modifies_d = char == "9" and lower.endswith("d")
            if self.buffer and (has_vowel or modifies_d):
                return self._feed(char)
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
        print("BaroKey: cannot connect to the IBus daemon", file=sys.stderr)
        raise SystemExit(1)
    factory = BaroEngineFactory(bus)
    bus.request_name(BUS_NAME, 0)
    IBus.main()


if __name__ == "__main__":
    main()
