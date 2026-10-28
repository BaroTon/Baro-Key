#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
LIB_DIR="$HOME/.local/lib/baro"
BIN_DIR="$HOME/.local/bin"
USER_COMPONENT="$DATA_HOME/ibus/component/baro.xml"
SYSTEM_COMPONENT="/usr/share/ibus/component/baro.xml"

if [ "$EUID" -eq 0 ]; then
    echo "Chạy script này bằng user thường (không dùng sudo)." >&2
    exit 1
fi

if ! python3 -c 'import gi; gi.require_version("IBus", "1.0"); from gi.repository import IBus' 2>/dev/null; then
    echo "Thiếu python3-gi hoặc gir1.2-ibus-1.0. Cài bằng:" >&2
    echo "  sudo apt install python3-gi gir1.2-ibus-1.0" >&2
    exit 1
fi

echo "Đang cài BARO vào $LIB_DIR ..."
install -d "$LIB_DIR" "$LIB_DIR/bin" "$LIB_DIR/share" "$BIN_DIR" "$DATA_HOME/applications"
rm -rf "$LIB_DIR/baro"
cp -a "$ROOT_DIR/baro" "$LIB_DIR/"
install -m 755 "$ROOT_DIR/bin/baro-engine" "$LIB_DIR/bin/baro-engine"
install -m 755 "$ROOT_DIR/bin/baro-settings" "$LIB_DIR/bin/baro-settings"
ln -sfn "$LIB_DIR/bin/baro-engine" "$BIN_DIR/baro-engine"
ln -sfn "$LIB_DIR/bin/baro-settings" "$BIN_DIR/baro-settings"

sed "s|@EXEC@|$LIB_DIR/bin/baro-engine|g" \
    "$ROOT_DIR/data/baro.xml.in" > "$LIB_DIR/share/baro.xml"
sed "s|@EXEC@|$LIB_DIR/bin/baro-settings|g" \
    "$ROOT_DIR/desktop/baro-settings.desktop.in" > "$DATA_HOME/applications/baro-settings.desktop"

component_installed=0
if [ -f "$SYSTEM_COMPONENT" ] && cmp -s "$LIB_DIR/share/baro.xml" "$SYSTEM_COMPONENT"; then
    component_installed=1
elif install -m 644 "$LIB_DIR/share/baro.xml" "$SYSTEM_COMPONENT" 2>/dev/null; then
    component_installed=1
elif command -v pkexec >/dev/null 2>&1; then
    echo "IBus không đọc component trong thư mục user; cần quyền root để cài $SYSTEM_COMPONENT."
    if timeout 120 pkexec install -m 644 "$LIB_DIR/share/baro.xml" "$SYSTEM_COMPONENT"; then
        component_installed=1
    fi
fi

if [ "$component_installed" -eq 1 ]; then
    rm -f "$USER_COMPONENT"
else
    install -d "$(dirname -- "$USER_COMPONENT")"
    install -m 644 "$LIB_DIR/share/baro.xml" "$USER_COMPONENT"
    echo
    echo "Chưa cài được component hệ thống. BARO tạm dùng component trong $USER_COMPONENT,"
    echo "nhưng IBus chỉ đọc thư mục này khi có biến môi trường:"
    echo "  export IBUS_COMPONENT_PATH=\"$DATA_HOME/ibus/component:/usr/share/ibus/component\""
    echo "Cách khác: chạy lại script và đồng ý hộp thoại quyền root."
fi

if command -v ibus >/dev/null 2>&1; then
    ibus restart >/dev/null 2>&1 || true
fi

python3 - <<'PY' || true
from gi.repository import Gio, GLib
settings = Gio.Settings.new("org.gnome.desktop.input-sources")
sources = [tuple(item) for item in settings.get_value("sources").unpack()]
if ("ibus", "baro") not in sources:
    sources.append(("ibus", "baro"))
    settings.set_value("sources", GLib.Variant("a(ss)", sources))
    print("Đã thêm BARO vào danh sách nguồn nhập (Super+Space để chọn).")
else:
    print("BARO đã có trong danh sách nguồn nhập.")
PY

echo
echo "Xong. Chọn BARO bằng Super+Space, hoặc vào Settings → Keyboard → Input Sources."
echo "Chuyển Việt/Anh trong BARO: Ctrl + \`"
if [ -n "${GTK_IM_MODULE:-}" ] && [ "${GTK_IM_MODULE}" = "fcitx" ]; then
    echo
    echo "Lưu ý: phiên hiện tại đang trỏ GTK/Qt sang Fcitx5, và Fcitx5 đang giữ tên D-Bus"
    echo "org.freedesktop.IBus nên IBus/BARO chưa chạy được. Chạy 'im-config -n ibus'"
    echo "rồi đăng xuất/đăng nhập lại."
fi
