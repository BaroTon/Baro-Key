#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
LIB_DIR="$HOME/.local/lib/baro"
BIN_DIR="$HOME/.local/bin"
SYSTEM_COMPONENT="/usr/share/ibus/component/baro.xml"

rm -rf "$LIB_DIR"
rm -f "$BIN_DIR/baro-engine" "$BIN_DIR/baro-settings"
rm -f "$DATA_HOME/ibus/component/baro.xml"
rm -f "$DATA_HOME/applications/baro-settings.desktop"

if [ -e "$SYSTEM_COMPONENT" ]; then
    if rm -f "$SYSTEM_COMPONENT" 2>/dev/null; then
        :
    elif command -v pkexec >/dev/null 2>&1; then
        timeout 120 pkexec rm -f "$SYSTEM_COMPONENT" || true
    fi
fi

python3 - <<'PY' || true
from gi.repository import Gio, GLib
settings = Gio.Settings.new("org.gnome.desktop.input-sources")
sources = [tuple(item) for item in settings.get_value("sources").unpack()]
filtered = [item for item in sources if item != ("ibus", "baro")]
if filtered != sources:
    settings.set_value("sources", GLib.Variant("a(ss)", filtered))
PY

if command -v ibus >/dev/null 2>&1; then
    ibus restart >/dev/null 2>&1 || true
fi

echo "Đã gỡ BARO. Cấu hình người dùng giữ nguyên tại ~/.config/baro/ (xoá nếu không cần)."
