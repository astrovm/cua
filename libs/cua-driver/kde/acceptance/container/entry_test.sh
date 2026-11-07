#!/bin/bash
# Runs inside the disposable KWin session. KWin is already up, as on a real desktop.
S=$1; LOG=/tmp/inst.log
release(){ mkdir -p /tmp/release /tmp/stage; cp /bin-under-test/cua-driver /tmp/stage/; printf '#!/bin/sh\n' > /tmp/stage/cua-cursor-theme; chmod +x /tmp/stage/cua-cursor-theme; tar czf /tmp/release/v$1.tar.gz -C /tmp/stage cua-driver cua-cursor-theme; }
install(){ release "$1"; PATH=/ctr/fake:$PATH CUA_DRIVER_RS_VERSION=$1 bash /scripts/install.sh --no-modify-path >$LOG 2>&1; echo "$S install $1 exit=$?"; grep -E 'KWin desktop entry|^error' $LOG | sed "s|^|$S   |" | cut -c1-200; }
E=$XDG_DATA_HOME/applications/ai.cua.driver.release.desktop
show(){ if [ -f "$E" ]; then echo "$S entry present: $(grep ^Exec= "$E" | sed "s|$ROOT|<root>|")"; else echo "$S entry absent"; fi; echo "$S real binary: $(readlink -f "$HOME/.local/bin/cua-driver" | sed "s|$ROOT|<root>|")"; }
check(){ python3 /ctr/e2e.py capture "$S" "$HOME/.local/bin/cua-driver"; }
store(){ gdbus call --session --dest org.freedesktop.impl.portal.PermissionStore --object-path /org/freedesktop/impl/portal/PermissionStore --method org.freedesktop.impl.portal.PermissionStore."$@"; }
desk(){ N=${N:-4} python3 /ctr/e2e.py desktopspeed "$1" "$2"; }
case "$S" in
  before|after) install 0.30.0; show; check;;
  update) install 0.30.0; show; install 0.30.1; show; check;;
  noflag) install 0.30.0; show; unset CUA_DRIVER_RS_ENABLE_WAYLAND; check;;
  uninstall) install 0.30.0; show
    mkdir -p /tmp/fid; printf '#!/bin/sh\nif [ "$1" = -u ]; then echo 1000; else /usr/bin/id "$@"; fi\n' > /tmp/fid/id; chmod +x /tmp/fid/id
    mkdir -p "$(dirname "$E")"; cp "$E" /tmp/kept.desktop
    PATH=/tmp/fid:$PATH bash /scripts/uninstall.sh >/tmp/un.log 2>&1; echo "$S uninstall exit=$?"; grep -E 'desktop' /tmp/un.log | sed "s|$ROOT|<root>|;s|^|$S   |"; show
    sed -i 's|^Exec=.*|Exec="/opt/other/cua-driver" serve|' /tmp/kept.desktop; cp /tmp/kept.desktop "$E"; release 0.30.0
    install 0.30.0 >/dev/null; sed -i 's|^Exec=.*|Exec="/opt/other/cua-driver" serve|' "$E"
    PATH=/tmp/fid:$PATH bash /scripts/uninstall.sh >/tmp/un2.log 2>&1; echo "$S uninstall with a foreign entry exit=$?"; show;;
  consent1) desk "$S" /bin-under-test/cua-driver;;
  deny-nogrant) store SetPermission screenshot true screenshot '' "['no']" >/dev/null; echo "$S store: $(store Lookup screenshot screenshot)"; desk "$S" /bin-under-test/cua-driver;;
  deny-entry) install 0.30.0; show; store SetPermission screenshot true screenshot '' "['no']" >/dev/null; echo "$S store: $(store Lookup screenshot screenshot)"; desk "$S" "$HOME/.local/bin/cua-driver";;
  grant-desktop) install 0.30.0; show; desk "$S" "$HOME/.local/bin/cua-driver";;
esac
