#!/bin/bash
# Run a check on a driver binary in real KWin, inside a container. Your desktop is not touched.
#   [DISTRO=debian13|fedora45] run.sh <altgr|typeroute|frame|capture|desktopspeed|text|bridge|monitors|x11|keys> <label> <binary> [VAR=value...]
# layouts (XKB_LAYOUTS=de,us) and long are in layouts.py. HARNESS_TIMEOUT overrides the 170 s cap.
# VARs: LAYOUT=two  XWAYLAND=1  XKB_VARIANT=altgr-intl  OUTPUT_SCALE=1.25  NOGRANT=1  GRANT_BIN=/bin-under-test/<name>  N=31
# keys also needs XWAYLAND=1. With CHROME_DIR=/opt/google/chrome in the environment it types into that Chrome too.
# The portal's consent dialogs are clicked by the test, inside this throwaway session.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
MODE=$1; LABEL=$2; BIN=$(readlink -f "$3"); shift 3
ENVS=(); for v in "$@"; do ENVS+=(-e "$v"); done
SCRIPT=(/ctr/e2e.py "$MODE" "$LABEL" "/bin-under-test/$(basename "$BIN")")
MOUNTS=()
RUNNER=(python3)
if [ "$MODE" = keys ]; then
    SCRIPT=(/ctr/keys.py "/bin-under-test/$(basename "$BIN")")
    [ -n "${CHROME_DIR:-}" ] && MOUNTS=(-v "$CHROME_DIR:/chrome:ro")
fi
GREP="^($LABEL|KEYS|  \[portal)|Traceback|File \"/ctr|Segmentation"
if [ "$MODE" = nativetest ]; then
    # The canonical manual test: <binary> is the driver, its folder also holds the test binary as kwin_native_capture_test.
    SCRIPT=(/bin-under-test/kwin_native_capture_test --ignored --nocapture --test-threads=1)
    ENVS+=(-e CUA_TEST_DRIVER_BIN=/bin-under-test/cua-driver -e CUA_TEST_REQUIRE_DRIVER_BIN=1 -e CUA_E2E_UNRESTRICTED_GUI=1 -e RUST_BACKTRACE=1)
    GREP="."; RUNNER=()
fi
if [ "$MODE" = layouts ] || [ "$MODE" = long ] || [ "$MODE" = modlog ] || [ "$MODE" = texts ] || [ "$MODE" = nodisplay ] || [ "$MODE" = refusal ] || [ "$MODE" = capsfirst ] || [ "$MODE" = hungx ]; then
    SCRIPT=(/ctr/layouts.py "/bin-under-test/$(basename "$BIN")" "$MODE")
fi
IMAGE=cu-kde-acceptance${DISTRO:+-$DISTRO}
podman image exists "$IMAGE" || nice -n 10 podman build --cpu-period 100000 --cpu-quota 400000 -q -t "$IMAGE" -f "$HERE/Containerfile${DISTRO:+.$DISTRO}" "$HERE" >/dev/null
# /dev/dri gives KWin OpenGL, which its screenshot API needs. /dev/fuse is for the document portal.
# Core dumps go to the host's handler from any container, and these sessions crash on teardown, so DrKonqi would pop up
# on the real desktop. The kernel skips piped dumps when the limit is 1.
timeout ${HARNESS_TIMEOUT:-170} nice -n 10 podman run --rm --cpus 2 --ulimit core=1:1 --memory 6g --memory-swap 6g --security-opt label=disable --network=none \
    --shm-size=1g --device /dev/fuse --cap-add SYS_ADMIN --device /dev/dri --group-add keep-groups "${ENVS[@]}" \
    -v "$(dirname "$BIN"):/bin-under-test:ro" -v "$HERE:/ctr:ro" ${SHOTS:+-v "$SHOTS:/shots"} "${MOUNTS[@]}" "$IMAGE" \
    /ctr/sess.sh "${RUNNER[@]}" "${SCRIPT[@]}" 2>&1 |
    grep -E "$GREP" | grep -v "^dbus-daemon" | cut -c1-${HARNESS_CUT:-400}
