#!/usr/bin/env bash
set -euo pipefail

if [ "${BARO_TEST_IN_SESSION:-}" != "1" ]; then
    export BARO_TEST_IN_SESSION=1
    exec dbus-run-session -- "$0" "$@"
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"

cleanup() {
    if [ -n "${DAEMON_PID:-}" ]; then
        kill "$DAEMON_PID" 2>/dev/null || true
        wait "$DAEMON_PID" 2>/dev/null || true
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$TMP_DIR/component" "$TMP_DIR/config" "$TMP_DIR/cache" "$TMP_DIR/data"
sed "s|@EXEC@|$ROOT_DIR/bin/baro-engine|g" \
    "$ROOT_DIR/data/baro.xml.in" > "$TMP_DIR/component/baro.xml"
if [ -f /usr/share/ibus/component/simple.xml ]; then
    cp /usr/share/ibus/component/simple.xml "$TMP_DIR/component/simple.xml"
fi

export HOME="$TMP_DIR"
export XDG_CONFIG_HOME="$TMP_DIR/config"
export XDG_CACHE_HOME="$TMP_DIR/cache"
export XDG_DATA_HOME="$TMP_DIR/data"
export IBUS_ADDRESS="unix:path=$TMP_DIR/ibus"
export IBUS_COMPONENT_PATH="$TMP_DIR/component"

ibus-daemon \
    --address="$IBUS_ADDRESS" \
    --panel=disable \
    --emoji-extension=disable \
    --xim=false \
    --config=disable \
    --cache=none >"$TMP_DIR/daemon.log" 2>&1 &
DAEMON_PID=$!

for _ in $(seq 1 100); do
    if ibus list-engine 2>/dev/null | grep -q "baro - BARO"; then
        break
    fi
    sleep 0.1
done

python3 "$ROOT_DIR/tests/ibus_daemon_test.py"
