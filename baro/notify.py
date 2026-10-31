"""Small desktop-notification helper shared by BaroKey and its IBus engine."""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

APP_NAME = "BaroKey"


_KEY_LABELS = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "super": "Super",
    "grave": "`",
    "space": "Space",
    "tab": "Tab",
    "return": "Enter",
    "backslash": "\\",
    "bracketleft": "[",
    "bracketright": "]",
    "semicolon": ";",
    "apostrophe": "'",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "minus": "-",
    "equal": "=",
    "backspace": "Backspace",
    "escape": "Esc",
    "page_up": "Page Up",
    "page_down": "Page Down",
    "scroll_lock": "Scroll Lock",
}


def key_label(name: str) -> str:
    """Human label for one key name: "f9" -> "F9", "page_up" -> "Page Up"."""
    name = str(name).lower()
    if name in _KEY_LABELS:
        return _KEY_LABELS[name]
    if len(name) == 1 or (name[0] == "f" and name[1:].isdigit()):
        return name.upper()
    return name.replace("_", " ").title()


def shortcut_label(spec: str) -> str:
    return " + ".join(key_label(part) for part in str(spec).lower().split("+"))


def send(
    title: str,
    body: str,
    icon: str = "barokey",
    timeout: int = 3500,
) -> bool:
    """Send one notification; never raise if the desktop has no notification bus."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            None,
        )
        proxy.call_sync(
            "Notify",
            GLib.Variant(
                "(susssasa{sv}i)",
                (APP_NAME, 0, icon, title, body, [], {}, timeout),
            ),
            Gio.DBusCallFlags.NONE,
            1200,
            None,
        )
        return True
    except Exception:
        return False
