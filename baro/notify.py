"""Small desktop-notification helper shared by BaroKey and its IBus engine."""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

APP_NAME = "BaroKey"


def shortcut_label(spec: str) -> str:
    names = {
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
    }
    parts = [names.get(part, part.upper()) for part in str(spec).lower().split("+")]
    return " + ".join(parts)


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
