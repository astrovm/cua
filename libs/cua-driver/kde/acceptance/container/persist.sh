#!/bin/bash
# Two sessions with one data home, as a logout and login. No entry, so desktop capture uses the portal.
export KEEP_DATA=/tmp/keep; mkdir -p "$KEEP_DATA"
echo "persist session 1"; /ctr/sess.sh bash /ctr/entry_test.sh consent1 2>&1 | grep -E '^consent1|^  \[portal' | sed 's/^/persist /'
echo "persist permission db: $(ls "$KEEP_DATA/flatpak/db" 2>/dev/null | tr '\n' ' ')"
echo "persist session 2"; /ctr/sess.sh bash /ctr/entry_test.sh consent1 2>&1 | grep -E '^consent1|^  \[portal' | sed 's/^/persist /'
