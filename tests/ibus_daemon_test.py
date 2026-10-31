"""End-to-end typing test through a private ibus-daemon.

Run through tests/run_ibus_test.sh, which starts the daemon with a component
file pointing at this checkout's bin/baro-engine.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

ENGINE = "baro"
failures = 0


def set_config(**values) -> None:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "baro" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    config.update(values)
    path.write_text(json.dumps(config), encoding="utf-8")


def set_method(method: str) -> None:
    set_config(method=method)


def pump(ms: int = 50) -> None:
    context = GLib.MainContext.default()
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        context.iteration(False)
        time.sleep(0.001)


def connect() -> IBus.Bus:
    IBus.init()
    end = time.monotonic() + 10
    while time.monotonic() < end:
        bus = IBus.Bus()
        if bus.is_connected():
            return bus
        time.sleep(0.1)
    sys.exit("cannot connect to ibus-daemon")


class App:
    def __init__(self, bus: IBus.Bus, name: str, purpose=IBus.InputPurpose.FREE_FORM):
        self.text = ""
        self.commits: list[str] = []
        self.preedit = ""
        self.ic = bus.create_input_context(name)
        self.ic.set_capabilities(IBus.Capabilite.FOCUS | IBus.Capabilite.PREEDIT_TEXT)
        self.ic.connect("commit-text", self.on_commit)
        self.ic.connect("update-preedit-text", self.on_preedit)
        self.ic.connect("hide-preedit-text", self.on_hide)
        self.ic.set_content_type(purpose, 0)
        self.ic.focus_in()
        for _ in range(50):
            if bus.set_global_engine(ENGINE):
                break
            pump(100)
        pump(500)
        engine = self.ic.get_engine()
        if engine is None or engine.get_name() != ENGINE:
            sys.exit("the BARO engine did not start")

    def on_commit(self, _ic, text):
        self.commits.append(text.get_text())
        self.text += text.get_text()

    def on_preedit(self, _ic, text, _cursor, visible):
        self.preedit = text.get_text() if visible else ""

    def on_hide(self, _ic):
        self.preedit = ""

    def key(self, char: str) -> bool:
        keyval = IBus.unicode_to_keyval(char)
        replies: list[bool] = []

        def done(ic, result):
            replies.append(ic.process_key_event_async_finish(result))

        self.ic.process_key_event_async(keyval, 0, 0, -1, None, done)
        end = time.monotonic() + 5
        context = GLib.MainContext.default()
        while not replies and time.monotonic() < end:
            context.iteration(True)
        self.ic.process_key_event(keyval, 0, IBus.ModifierType.RELEASE_MASK)
        pump(40)
        return replies[0] if replies else False

    def combo(self, key, state: int) -> bool:
        """Press a key with modifiers (a shortcut) and wait for the reply."""
        keyval = IBus.unicode_to_keyval(key) if isinstance(key, str) else key
        replies: list[bool] = []

        def done(ic, result):
            replies.append(ic.process_key_event_async_finish(result))

        self.ic.process_key_event_async(keyval, 0, state, -1, None, done)
        end = time.monotonic() + 5
        context = GLib.MainContext.default()
        while not replies and time.monotonic() < end:
            context.iteration(True)
        pump(150)
        return replies[0] if replies else False

    def type(self, text: str) -> None:
        for char in text:
            if not self.key(char):
                self.text += char

    def reset(self) -> None:
        self.ic.reset()
        pump(100)

    def close(self) -> None:
        self.ic.focus_out()
        pump(100)


def check(ok: bool, what: str, got) -> None:
    global failures
    if not ok:
        failures += 1
        print(f"FAIL {what}: {got!r}")


def main() -> int:
    bus = connect()

    app = App(bus, "telex")
    app.type("vieejt")
    check(app.preedit == "việt", "telex preedit", app.preedit)
    app.key(" ")
    check(app.commits == ["việt"], "telex commit", app.commits)
    app.close()

    set_method("vni")
    app = App(bus, "vni")
    app.ic.set_content_type(IBus.InputPurpose.FREE_FORM, 0)
    app.type("d9")
    check(app.preedit == "đ", "vni d9 preedit", app.preedit)
    app.type("i vie6t5")
    app.key(" ")
    check(app.commits == ["đi", "việt"], "vni commits", app.commits)
    app.close()

    set_method("telex")
    app = App(bus, "invalid")
    app.type("asd")
    check(app.preedit == "asd", "invalid preedit", app.preedit)
    app.key(" ")
    check(app.commits == ["asd"], "invalid commit", app.commits)
    app.close()

    app = App(bus, "reset")
    app.type("viee")
    check(app.preedit == "viê", "reset preedit", app.preedit)
    app.reset()
    check(app.preedit == "", "reset clears preedit", app.preedit)
    app.type("a ")
    check(app.commits == ["a"], "reset starts a new word", app.commits)
    app.close()

    app = App(bus, "bamboo")
    bamboo_cases = (
        ("anw", "ăn"),
        ("comw", "cơm"),
        ("chuaw", "chưa"),
        ("barr", "bar"),
        ("barro", "baro"),
        ("baro", "bảo"),
        ("stress", "stress"),
        ("wwork", "work"),
        ("chEe", "chÊ"),
        ("CHAOf", "CHÀO"),
    )
    for keys, expected in bamboo_cases:
        app.type(keys)
        check(app.preedit == expected, f"{keys} preedit", app.preedit)
        app.key(" ")
        check(app.text.endswith(expected), f"{keys} commit", app.text)
    app.close()

    app = App(bus, "password", IBus.InputPurpose.PASSWORD)
    app.type("aa dd ")
    check(app.commits == [], "password has no commits", app.commits)
    check(app.preedit == "", "password has no preedit", app.preedit)
    app.close()

    # Shortcuts can be any key combination, not just the built-in presets.
    # Vietnamese mode turns "aa" into "â"; English mode leaves it alone.
    set_config(
        shortcut_toggle="ctrl+alt+k",
        shortcut_enable="f9",
        english_mode=False,
        start_enabled=True,
        method="telex",
    )
    ctrl_alt = IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK
    ctrl_shift = IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK

    def types_vietnamese(label: str) -> bool:
        app.reset()
        app.commits.clear()
        app.text = ""
        app.type("aa ")
        return app.text.startswith("â")

    app = App(bus, "custom-shortcuts")
    check(types_vietnamese("start"), "starts in Vietnamese mode", app.text)
    check(app.combo("k", ctrl_alt), "ctrl+alt+k is consumed", None)
    check(not types_vietnamese("ctrl+alt+k"), "ctrl+alt+k switches to English", app.text)
    app.combo("k", ctrl_alt)
    check(types_vietnamese("back"), "ctrl+alt+k switches back to Vietnamese", app.text)
    check(app.combo(IBus.KEY_F9, 0), "F9 is consumed", None)
    check(not types_vietnamese("f9"), "F9 turns the engine off", app.text)
    app.combo(IBus.KEY_F9, 0)
    check(types_vietnamese("f9 again"), "F9 turns the engine on again", app.text)
    check(not app.combo("v", ctrl_shift), "old ctrl+shift+v is no longer bound", None)
    check(types_vietnamese("unbound"), "old shortcut did not change the mode", app.text)
    app.close()

    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("IBus daemon test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
