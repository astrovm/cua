#!/bin/bash
# Run the owner e2e test in real KWin, in a container. [DISTRO=...] runtest.sh <label> <driver binary> <test binary> [VAR=value...]
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LABEL=$1; BIN=$(readlink -f "$2"); TESTBIN=$(readlink -f "$3"); shift 3
ENVS=(); for v in "$@"; do ENVS+=(-e "$v"); done
IMAGE=cu-kde-acceptance${DISTRO:+-$DISTRO}
podman image exists "$IMAGE" || nice -n 10 podman build --cpu-period 100000 --cpu-quota 400000 -q -t "$IMAGE" -f "$HERE/Containerfile${DISTRO:+.$DISTRO}" "$HERE" >/dev/null
timeout 170 nice -n 10 podman run --rm --cpus 2 --ulimit core=1:1 --memory 6g --memory-swap 6g --security-opt label=disable --network=none \
    --shm-size=1g --device /dev/fuse --cap-add SYS_ADMIN --device /dev/dri --group-add keep-groups "${ENVS[@]}" \
    -v "$(dirname "$BIN"):/bin-under-test:ro" -v "$(dirname "$TESTBIN"):/test-under-test:ro" -v "$HERE:/ctr:ro" "$IMAGE" \
    /ctr/sess.sh python3 /ctr/rt.py "$LABEL" "/bin-under-test/$(basename "$BIN")" "/test-under-test/$(basename "$TESTBIN")" a_screenshot_pixel_lands_on_target_on_every_output 2>&1 |
    grep -E "^($LABEL)|Traceback|File \"/ctr|Segmentation" | cut -c1-700
