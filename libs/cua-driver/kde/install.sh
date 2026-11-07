#!/bin/sh
# Install this branch's cua-driver on KDE Plasma, next to the official one.
#
#   install.sh                build in a container, then install
#   install.sh <binary>       install a binary you already built
#   install.sh --uninstall    go back to the official build
set -eu

DIR="$HOME/.local/lib/cua-driver-kde"
BIN="$DIR/cua-driver"
LINK="$HOME/.local/bin/cua-driver"
ENTRY="$HOME/.local/share/applications/cua-driver-kde.desktop"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

refresh() { kbuildsycoca6 >/dev/null 2>&1 || true; }

if [ "${1:-}" = "--uninstall" ]; then
    [ -f "$DIR/previous" ] || { echo "Nothing to undo: $DIR/previous is missing." >&2; exit 1; }
    ln -sfn "$(cat "$DIR/previous")" "$LINK"
    rm -f "$ENTRY" "$BIN" "$DIR/cua-cursor-theme" "$DIR/previous"
    refresh
    echo "Back to the official build: $("$LINK" --version)"
    exit 0
fi

if [ $# -ge 1 ]; then
    SRC=$1
else
    ROOT=$(CDPATH= cd -- "$HERE/../../.." && pwd)
    nice -n 10 podman build --cpu-period 100000 --cpu-quota 400000 -t cua-driver-kde-build -f "$HERE/Containerfile" "$HERE"
    nice -n 10 podman run --rm --cpus 4 -e CARGO_BUILD_JOBS=4 --security-opt label=disable \
        -v "$ROOT:/src" -v cua-driver-kde-cargo:/root/.cargo/registry \
        cua-driver-kde-build bash -lc \
        'cargo build --release -p cua-driver --features cua-driver/portal-input --locked'
    SRC="$ROOT/libs/cua-driver/rust/target/agent/release/cua-driver"
fi

mkdir -p "$DIR" "$(dirname "$LINK")" "$(dirname "$ENTRY")"
# Remember the official build once, so a reinstall can't lose the way back.
if [ ! -f "$DIR/previous" ] && [ -L "$LINK" ]; then
    readlink "$LINK" > "$DIR/previous"
fi
install -m 755 "$SRC" "$BIN.new"
mv -f "$BIN.new" "$BIN"
# The official package ships this helper beside the driver.
OFFICIAL=$(cat "$DIR/previous" 2>/dev/null || true)
if [ -n "$OFFICIAL" ] && [ -x "$(dirname "$OFFICIAL")/cua-cursor-theme" ]; then
    install -m 755 "$(dirname "$OFFICIAL")/cua-cursor-theme" "$DIR/cua-cursor-theme"
fi

# KWin only grants window capture and window management to an executable named
# by a desktop entry, matched on its exact path.
cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Cua Driver (KDE)
Exec=$BIN
NoDisplay=true
X-KDE-Wayland-Interfaces=org_kde_plasma_window_management,org_kde_kwin_keystate
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
EOF
refresh
ln -sfn "$BIN" "$LINK"
echo "Installed $("$LINK" --version) at $BIN"
echo "Restart your agents: running ones keep the old build."
