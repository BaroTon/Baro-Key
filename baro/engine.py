"""IBus engine for BaroKey."""

from __future__ import annotations

import os
import sys
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

from . import bamboo, core, notify  # noqa: E402
from .config import config_path, load, parse_shortcut_spec, save  # noqa: E402

ENGINE_NAME = "baro"
BUS_NAME = "org.freedesktop.IBus.Baro"

# Keys whose IBus name is not simply the lower-case spec name.
_KEY_ALIASES = {
    "backspace": "BackSpace",
    "iso_left_tab": "ISO_Left_Tab",
}

# What Shift turns a US-layout key into, so that "ctrl+shift+1" still matches
# when the client reports "exclam".
_SHIFTED_US = {
    ord("!"): ord("1"),
    ord("@"): ord("2"),
    ord("#"): ord("3"),
    ord("$"): ord("4"),
    ord("%"): ord("5"),
    ord("^"): ord("6"),
    ord("&"): ord("7"),
    ord("*"): ord("8"),
    ord("("): ord("9"),
    ord(")"): ord("0"),
    ord("_"): ord("-"),
    ord("+"): ord("="),
    ord("{"): ord("["),
    ord("}"): ord("]"),
    ord("|"): ord("\\"),
    ord(":"): ord(";"),
    ord('"'): ord("'"),
    ord("<"): ord(","),
    ord(">"): ord("."),
    ord("?"): ord("/"),
    ord("~"): ord("`"),
}


def key_to_keyval(name: str):
    """IBus keyval for a lower-case key name such as "k", "f9" or "page_up"."""
    name = name.lower()
    candidates = [_KEY_ALIASES.get(name), name, name.capitalize(), name.upper()]
    candidates.append("_".join(word.capitalize() for word in name.split("_")))
    if name.startswith("kp_"):
        candidates.append("KP_" + name[3:].capitalize())
    for candidate in candidates:
        if not candidate:
            continue
        keyval = IBus.keyval_from_name(candidate)
        if keyval and keyval != IBus.KEY_VoidSymbol:
            return int(keyval)
    return None


# Modifier keys that can form a modifier-only shortcut such as "alt+shift".
_CHORD_MODS = {
    IBus.KEY_Shift_L: "shift",
    IBus.KEY_Shift_R: "shift",
    IBus.KEY_Control_L: "ctrl",
    IBus.KEY_Control_R: "ctrl",
    IBus.KEY_Alt_L: "alt",
    IBus.KEY_Alt_R: "alt",
    IBus.KEY_Meta_L: "alt",
    IBus.KEY_Meta_R: "alt",
    IBus.KEY_Super_L: "super",
    IBus.KEY_Super_R: "super",
}
_ANY_MODIFIER = (
    IBus.ModifierType.CONTROL_MASK
    | IBus.ModifierType.SHIFT_MASK
    | IBus.ModifierType.MOD1_MASK
    | IBus.ModifierType.SUPER_MASK
)


# Diagnostics for shortcuts that "do nothing": create the flag file
#   ~/.cache/baro/debug-keys
# and the engine appends what it receives to ~/.cache/baro/keys.log. Only
# modifier keys, keys held with Ctrl/Alt/Super and function keys are logged,
# never ordinary typing, so no text ends up in the log.
def _debug_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "baro")


def debug_flag_path() -> str:
    return os.path.join(_debug_dir(), "debug-keys")


def debug_log_path() -> str:
    return os.path.join(_debug_dir(), "keys.log")


def parse_chord(spec: str):
    """The modifiers of a modifier-only spec like "alt+shift", else None."""
    parsed = parse_shortcut_spec(spec)
    if parsed is None or parsed[1] is not None:
        return None
    return frozenset(parsed[0])


def parse_shortcut(spec: str):
    """Return (keyval, ctrl, shift, alt, super) or None for an invalid spec."""
    parsed = parse_shortcut_spec(spec)
    if parsed is None:
        return None
    mods, key = parsed
    if key is None:  # modifier-only: handled by parse_chord / _track_chord
        return None
    keyval = key_to_keyval(key)
    if keyval is None:
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
        self._debug("ACTION  turn the engine on / off")
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

    # Modifier-only shortcuts ("alt+shift", as in EVKey) fire when the modifiers
    # are released, provided nothing else was pressed while they were down.
    # Class-level defaults so the state exists before the first key event.
    _chord_held: frozenset = frozenset()   # modifier keyvals currently down
    _chord_peak: frozenset = frozenset()   # modifier names held at the same time
    _chord_dirty = False                    # a normal key was pressed meanwhile
    _chord_fired = False                    # already fired during this hold

    def _debug(self, text: str) -> None:
        try:
            if not os.path.exists(debug_flag_path()):
                return
            path = debug_log_path()
            if os.path.exists(path) and os.path.getsize(path) > 200_000:
                os.replace(path, path + ".old")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(f"{time.strftime('%H:%M:%S')} {text}\n")
        except OSError:
            pass

    def _debug_key(self, keyval, keycode, state) -> None:
        name = IBus.keyval_name(keyval) or hex(keyval)
        released = bool(state & IBus.ModifierType.RELEASE_MASK)
        interesting = (
            keyval in _CHORD_MODS
            or keyval in MODIFIER_KEYS
            or bool(
                state
                & (
                    IBus.ModifierType.CONTROL_MASK
                    | IBus.ModifierType.MOD1_MASK
                    | IBus.ModifierType.SUPER_MASK
                )
            )
            or (name.startswith("F") and name[1:].isdigit())
        )
        if not interesting:
            return
        self._debug(
            f"{'release' if released else 'press  '} {name:<12} keycode={keycode} "
            f"state=0x{int(state):x} held={sorted(self._chord_peak)} "
            f"dirty={self._chord_dirty} "
            f"toggle={self.config.get('shortcut_toggle')!r} "
            f"enable={self.config.get('shortcut_enable')!r} "
            f"mode={'on' if self._enabled else 'off'}/"
            f"{'vi' if self.vietnamese else 'en'}"
        )

    def _reset_chord(self) -> None:
        self._chord_held = frozenset()
        self._chord_peak = frozenset()
        self._chord_dirty = False
        self._chord_fired = False

    def _track_chord(self, keyval, state) -> None:
        released = bool(state & IBus.ModifierType.RELEASE_MASK)
        mod = _CHORD_MODS.get(keyval)
        if mod is None:
            if not released and self._chord_held:
                if state & _ANY_MODIFIER:
                    self._chord_dirty = True
                else:
                    # No modifier is really down: a release event was lost.
                    self._reset_chord()
            return
        if not released:
            self._chord_held = self._chord_held | {keyval}
            self._chord_peak = self._chord_peak | {mod}
            return
        if self._chord_held and not self._chord_dirty and not self._chord_fired:
            self._chord_fired = self._run_chord(self._chord_peak)
        self._chord_held = self._chord_held - {keyval}
        if not self._chord_held:
            self._reset_chord()

    def _run_chord(self, peak) -> bool:
        """Run the action bound to exactly these modifiers; True if one ran."""
        if peak and peak == parse_chord(
            self.config.get("shortcut_enable", "ctrl+shift+b")
        ):
            self._toggle_enabled()
            return True
        if peak and peak == parse_chord(
            self.config.get("shortcut_toggle", "ctrl+shift+v")
        ):
            self._toggle()
            return True
        return False

    def _matches_shortcut(self, keyval, state, spec: str) -> bool:
        parsed = parse_shortcut(spec)
        if parsed is None:
            return False
        expected, ctrl, shift, alt, super_key = parsed
        if state & IBus.ModifierType.SHIFT_MASK:
            if ord("A") <= keyval <= ord("Z"):
                keyval += 32
            else:
                keyval = _SHIFTED_US.get(keyval, keyval)
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
        preedit = IBus.Text.new_from_string(text)
        # Ask the client not to underline the word being typed. Apps that
        # honour IBus attributes then show it like ordinary text; the rest
        # keep drawing their own composition style.
        preedit.append_attribute(
            IBus.AttrType.UNDERLINE, IBus.AttrUnderline.NONE, 0, len(text)
        )
        self.update_preedit_text(preedit, len(text), True)

    def _flush(self) -> None:
        if self.buffer:
            text = self._display() or self.buffer
            self.commit_text(IBus.Text.new_from_string(text))
            self._clear_word()
        self.hide_preedit_text()

    def _toggle(self) -> None:
        self._debug("ACTION  switch Vietnamese / English")
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
        self._debug(f"focus-in  engine pid={os.getpid()}")
        self._reset_chord()
        old_mtime = self._config_mtime
        self._reload_config()
        if self._config_mtime != old_mtime:
            self._enabled = bool(self.config.get("start_enabled", True))
            self.vietnamese = not bool(self.config.get("english_mode", False))
            self._update_mode_property()
        self._sync_engine()
        self._register_properties()

    def do_focus_out(self):
        self._reset_chord()
        self._flush()

    def do_reset(self):
        self._reset_chord()
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
            self._reset_chord()
            return False

        self._debug_key(keyval, keycode, state)
        self._track_chord(keyval, state)

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
