#!/usr/bin/env python3
"""Render every BaroKey settings page to docs/screenshots/*.png.

Runs the real GTK window and snapshots it with the GSK renderer, so it needs a
graphical session but no screenshot tool. Uses a throw-away config directory.
"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="barokey-shots-")

loader = importlib.machinery.SourceFileLoader(
    "baro_settings", os.path.join(ROOT, "bin", "baro-settings")
)
spec = importlib.util.spec_from_loader("baro_settings", loader)
app_mod = importlib.util.module_from_spec(spec)
loader.exec_module(app_mod)

from gi.repository import Gio, GLib, Gtk  # noqa: E402

# (file name, page, theme, style)
SHOTS = [
    ("overview", "overview", "dark", "default"),
    ("method", "method", "dark", "default"),
    ("charset", "charset", "dark", "default"),
    ("options", "options", "dark", "default"),
    ("shortcuts", "shortcuts", "dark", "default"),
    ("appearance", "appearance", "dark", "default"),
    ("about", "about", "dark", "default"),
    ("overview-light", "overview", "light", "default"),
    ("tahoe-overview-light", "overview", "light", "tahoe"),
    ("tahoe-overview-dark", "overview", "dark", "tahoe"),
    ("tahoe-appearance-light", "appearance", "light", "tahoe"),
]


def snapshot(window, path):
    paintable = Gtk.WidgetPaintable.new(window)
    snap = Gtk.Snapshot()
    paintable.snapshot(snap, window.get_width(), window.get_height())
    node = snap.to_node()
    if node is None:
        return False
    texture = window.get_native().get_renderer().render_texture(node, None)
    texture.save_to_png(path)
    return True


def run(app):
    window = app.window
    window.set_default_size(1024, 720)
    queue = list(SHOTS)

    def dialog_shot():
        app.ui_style = "default"
        window.config["ui_style"] = "default"
        window.apply_style_class()
        window._sync_style()
        window.config["theme"] = "dark"
        window._sync_theme()
        app.apply_theme("dark")
        dialog = app_mod.ShortcutDialog(
            window, "Chuyển đổi Việt / Anh", app_mod.SHORTCUT_PRESETS["toggle"],
            "ctrl+alt+k", "ctrl+shift+v", "ctrl+shift+b", "Bật / Tắt bộ gõ", lambda _s: None,
        )
        dialog.present()

        def shoot_dialog():
            if not snapshot(dialog, os.path.join(OUT, "shortcut-dialog.png")):
                return True
            print("saved shortcut-dialog", flush=True)
            dialog.close()
            app.quit()
            return False

        GLib.timeout_add(800, shoot_dialog)
        return False

    def step():
        if not queue:
            return dialog_shot()
        name, page, theme, style = queue.pop(0)
        app.ui_style = style
        window.config["ui_style"] = style
        window.apply_style_class()
        window._sync_style()
        window.config["theme"] = theme
        window._sync_theme()
        app.apply_theme(theme)
        window._show_page(page)

        def shoot():
            if not snapshot(window, os.path.join(OUT, f"{name}.png")):
                return True  # window not drawn yet, retry
            print("saved", name, flush=True)
            GLib.timeout_add(100, step)
            return False

        GLib.timeout_add(600, shoot)
        return False

    GLib.timeout_add(800, step)


def main():
    os.makedirs(OUT, exist_ok=True)
    app = app_mod.BaroKeyApp()
    # Do not hand off to an already running BaroKey window.
    app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
    app.connect_after("activate", run)
    app.run([sys.argv[0]])


if __name__ == "__main__":
    main()
