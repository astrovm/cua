#!/bin/bash
# Real-desktop checks. Opens a small test window, moves your pointer and takes focus
# for about a minute, so don't type meanwhile. Ground truth is what the test window
# really received, never the driver's reply. Needs python3 with PyQt6 and pyatspi.
#
#   run.sh            18 checks. One fails by design: Qt dropdown items (see README)
#   run.sh speed      latency through the MCP route agents use
cd "$(dirname "$0")" || exit 1
mkdir -p results
if [ "${1:-}" = speed ]; then exec python3 mcp_speed.py; fi
export CUA_BIN="$HOME/.local/bin/cua-driver" CUA_SOCK=/tmp/cua-kde-accept.sock
rm -f "$CUA_SOCK"
CUA_DRIVER_RS_ENABLE_WAYLAND=1 "$CUA_BIN" serve --socket "$CUA_SOCK" --pid-file /tmp/cua-kde-accept.pid >/tmp/cua-kde-accept.log 2>&1 &
daemon=$!
trap 'kill "$daemon" 2>/dev/null; rm -f "$CUA_SOCK"' EXIT
python3 -c 'import time; time.sleep(1.5)'
python3 accept.py
