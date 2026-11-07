#!/bin/bash
# Disposable KDE session for tests, only ever run inside a container. SCALE and XKB_VARIANT are optional.
ROOT=$(mktemp -d /tmp/s-XXXX); mkdir -p $ROOT/{run,config,cache,data,home/.cua-driver,home/Pictures,scratch}; chmod 700 $ROOT/run
echo '{"telemetry_enabled":false}' > $ROOT/home/.cua-driver/config.json
if [ -n "${XKB_LAYOUTS:-}" ]; then printf '[Layout]\nLayoutList=%s\nVariantList=%s\nOptions=%s\nResetOldOptions=true\nUse=true\n' "$XKB_LAYOUTS" "${XKB_VARIANTS:-}" "${XKB_OPTIONS:-}" > $ROOT/config/kxkbrc; fi
[ -n "${XKB_VARIANT:-}" ] && printf '[Layout]\nLayoutList=us\nVariantList=%s\nUse=true\n' "$XKB_VARIANT" > $ROOT/config/kxkbrc
if [ -n "${GRANT_BIN:-}" ]; then mkdir -p $ROOT/data/applications; printf '[Desktop Entry]\nType=Application\nName=cua-driver\nExec=%s\nNoDisplay=true\nX-KDE-Wayland-Interfaces=%s\nX-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2\n' "$GRANT_BIN" "${GRANT_IFACES:-org_kde_plasma_window_management,org_kde_kwin_keystate}" > $ROOT/data/applications/cua-driver.desktop; fi
env -u DISPLAY -u WAYLAND_DISPLAY -u DBUS_SESSION_BUS_ADDRESS QT_QPA_PLATFORM=offscreen LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  HOME=$ROOT/home XDG_RUNTIME_DIR=$ROOT/run XDG_CONFIG_HOME=$ROOT/config XDG_CACHE_HOME=$ROOT/cache XDG_DATA_HOME=${KEEP_DATA:-$ROOT/data} \
  KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1 KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 \
  CUA_DRIVER_RS_ENABLE_WAYLAND=1 XDG_MENU_PREFIX=plasma- SCRATCH_DIR=$ROOT/scratch ROOT=$ROOT SCALE=${SCALE:-} \
  dbus-run-session -- bash -c '
    [ -n "${GRANT_BIN:-}" ] && QT_QPA_PLATFORM=offscreen kbuildsycoca6 --noincremental >/dev/null 2>&1
    if [ -n "${NOGRANT:-}" ]; then unset KWIN_SCREENSHOT_NO_PERMISSION_CHECKS KWIN_WAYLAND_NO_PERMISSION_CHECKS; fi
    # Before KWin: it activates the portal at startup on some releases, and a portal started without these has no KDE backend.
    gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.UpdateActivationEnvironment "{\"XDG_CURRENT_DESKTOP\":\"KDE\",\"QT_QPA_PLATFORM\":\"wayland\",\"WAYLAND_DISPLAY\":\"private\",\"QT_LINUX_ACCESSIBILITY_ALWAYS_ON\":\"1\",\"KDE_FULL_SESSION\":\"true\",\"KDE_SESSION_VERSION\":\"6\",\"QT_LOGGING_RULES\":\"xdp*=true\",\"G_MESSAGES_DEBUG\":\"all\"}" >/dev/null 2>&1
    pipewire >/dev/null 2>&1 & sleep .4; wireplumber >/dev/null 2>&1 &
    W=1600; H=900; [ -n "${LAYOUT:-}" ] && { W=1920; H=1080; }; [ -n "${XWAYLAND:-}" ] && { mkdir -p /tmp/.X11-unix; chmod 1777 /tmp/.X11-unix; }
    [ -n "${KWINCFG:-}" ] && echo "$KWINCFG" > $ROOT/config/kwinoutputconfig.json
    kwin_wayland --virtual --no-lockscreen --no-global-shortcuts --no-kactivities --socket private ${XWAYLAND:+--xwayland} ${LAYOUT:+--output-count 2} --width $W --height $H ${SCALE:+--scale $SCALE} >$ROOT/kwin.log 2>&1 &
    kw=$!; for i in $(seq 100); do [ -S $ROOT/run/private ] && break; sleep .05; done
    export WAYLAND_DISPLAY=private QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 QT_QPA_PLATFORM=wayland XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 XDG_SESSION_TYPE=wayland
    gdbus call --session --dest org.a11y.Bus --object-path /org/a11y/bus --method org.freedesktop.DBus.Properties.Set org.a11y.Status IsEnabled "<true>" >/dev/null 2>&1
    # LAYOUT: a portrait 1080p left of a landscape 1440p, both at 1.25, as on a real two-monitor desk.
    if [ "${LAYOUT:-}" = two ]; then sleep 1; kscreen-doctor output.Virtual-1.addCustomMode.2560.1440.60000.full >/dev/null 2>&1; sleep .5; m=$(kscreen-doctor -o 2>/dev/null | sed "s/\x1b\[[0-9;]*m//g" | grep -oE "[0-9]+:2560x1440@[0-9.]+" | head -1); kscreen-doctor output.Virtual-1.mode.${m%%:*} >/dev/null 2>&1; sleep .5; kscreen-doctor output.Virtual-0.rotation.right output.Virtual-0.scale.1.25 output.Virtual-0.position.0,0 output.Virtual-1.scale.1.25 output.Virtual-1.position.864,0 >/dev/null 2>&1; sleep 1; fi
    # LAYOUT=offset: only an output at (864,0) stays on. LAYOUT=negoff: two unrotated outputs, one at negative coordinates. LAYOUT=mixed: scale 1.0 left of scale 2.0, in either announcement order (MIXORDER=1 swaps which output is scaled).
    if [ "${LAYOUT:-}" = offset ]; then kscreen-doctor output.Virtual-1.position.864,0 >/dev/null 2>&1; sleep 1; kscreen-doctor output.Virtual-0.disable >/dev/null 2>&1; sleep 1; fi
    if [ "${LAYOUT:-}" = both ]; then kscreen-doctor output.Virtual-0.position.100,50 output.Virtual-1.position.2020,50 >/dev/null 2>&1; sleep 1; fi
    if [ "${LAYOUT:-}" = negoff ]; then kscreen-doctor output.Virtual-0.position.-1920,-200 output.Virtual-1.position.0,0 >/dev/null 2>&1; sleep 1; fi
    if [ "${LAYOUT:-}" = mixed ]; then if [ -n "${MIXORDER:-}" ]; then A=2; B=1; XA=960; else A=1; B=2; XA=1920; fi; kscreen-doctor output.Virtual-0.scale.$A output.Virtual-0.position.0,0 output.Virtual-1.scale.$B output.Virtual-1.position.$XA,0 >/dev/null 2>&1; sleep 1; fi
    if [ -n "${LAYOUT_DUMP:-}" ]; then sed "s/^/$LAYOUT_DUMP cfg: /" $ROOT/config/kwinoutputconfig.json; fi
    if [ -n "${LAYOUT_SHOW:-}" ]; then kscreen-doctor -o 2>/dev/null | sed "s/\x1b\[[0-9;]*m//g" | grep -E "^Output|Geometry|Scale|enabled|disabled" | sed "s/^/$LAYOUT_SHOW layout: /"; fi
    if [ -n "${XWAYLAND:-}" ]; then export DISPLAY=:0 XAUTHORITY=$(ls $ROOT/run/xauth_* 2>/dev/null | head -1); fi
    if [ -n "${OUTPUT_SCALE:-}" ]; then sleep 1; o=$(kscreen-doctor -o 2>/dev/null | sed "s/\x1b\[[0-9;]*m//g" | awk "/^Output:/{print \$3; exit}"); echo "scaling output [$o] to $OUTPUT_SCALE"; kscreen-doctor output.$o.scale.$OUTPUT_SCALE 2>&1 | tail -1; sleep 1; kscreen-doctor -o 2>/dev/null | sed "s/\x1b\[[0-9;]*m//g" | awk "/Scale|Geometry/"; fi
    "$@"; st=$?; kill $kw 2>/dev/null; exit $st' bash "$@"
