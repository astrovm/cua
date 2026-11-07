#!/usr/bin/env python3
"""Run a cua-driver-e2e test binary in the session, answering the portal's dialogs. rt.py <label> <driver> <test binary> <test name>"""
import os,subprocess as sp,sys,threading,time
import gi
gi.require_version("Atspi","2.0")
from gi.repository import Atspi
LABEL,DRIVER,TEST,NAME=sys.argv[1:5]
stop=threading.Event()
def approve():
    def walk(n,o):
        o.append(n)
        for i in range(min(n.get_child_count(),40)):
            c=n.get_child_at_index(i)
            if c: walk(c,o)
        return o
    while not stop.is_set():
        time.sleep(.5)
        try:
            d=Atspi.get_desktop(0)
            for i in range(d.get_child_count()):
                a=d.get_child_at_index(i)
                if a and "portal" in (a.get_name() or "").lower():
                    for n in walk(a,[]):
                        if n.get_role_name() in("button","push button") and n.get_name() in("Approve","Allow","Share","Save","OK"):
                            print(f"{LABEL} [portal dialog: clicked {n.get_name()}]",flush=True); n.get_action_iface().do_action(0); time.sleep(1)
        except Exception: pass
threading.Thread(target=approve,daemon=True).start()
env=dict(os.environ,CUA_TEST_DRIVER_BIN=DRIVER,RUST_BACKTRACE="0",CUA_TEST_DRIVER_STDERR="1")
p=sp.run([TEST,"--ignored","--exact",NAME,"--nocapture","--test-threads=1"],env=env,stdout=sp.PIPE,stderr=sp.STDOUT,text=True,timeout=140)
for l in p.stdout.splitlines()[-30:]: print(LABEL,l[:600],flush=True)
print(LABEL,"EXIT",p.returncode,flush=True)
stop.set()
