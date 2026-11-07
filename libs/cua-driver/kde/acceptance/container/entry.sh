#!/bin/bash
# Run the release installer in real KWin, permission checks on, and check what it grants. Your desktop is not touched.
#   entry.sh <before|after|update|noflag|uninstall|grant-desktop|deny-nogrant|deny-entry|persist> <binary> <folder with install.sh> [VAR=value...]
# `before` means a scripts folder without the entry. The binary is served as a local release by fake/curl.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
S=$1; BIN=$(readlink -f "$2"); SCRIPTS=$(readlink -f "$3"); shift 3
ENVS=(-e NOGRANT=1); for v in "$@"; do ENVS+=(-e "$v"); done
CMD=(/ctr/sess.sh bash /ctr/entry_test.sh "$S"); [ "$S" = persist ] && CMD=(/ctr/persist.sh)
IMAGE=cu-kde-acceptance
podman image exists "$IMAGE" || nice -n 10 podman build --cpu-period 100000 --cpu-quota 400000 -q -t "$IMAGE" -f "$HERE/Containerfile" "$HERE" >/dev/null
timeout 240 nice -n 10 podman run --rm --cpus 2 --ulimit core=1:1 --memory 6g --memory-swap 6g --security-opt label=disable --network=none \
    --shm-size=1g --device /dev/fuse --cap-add SYS_ADMIN --device /dev/dri --group-add keep-groups "${ENVS[@]}" \
    -v "$(dirname "$BIN"):/bin-under-test:ro" -v "$HERE:/ctr:ro" -v "$SCRIPTS:/scripts:ro" "$IMAGE" "${CMD[@]}" 2>&1 |
    grep -E "^($S|persist)|^  \[portal|Traceback|File \"/ctr|Segmentation" | cut -c1-230
