#!/usr/bin/env python3
"""Real KWin, real portal, real libei in a disposable session. Ground truth is the target window's own event log."""
import json,os,subprocess as sp,sys,threading,time,base64
import gi
gi.require_version("Atspi","2.0")
from gi.repository import Atspi
MODE,LABEL,BIN=sys.argv[1:4]; R=os.environ["SCRATCH_DIR"]; SOCK=R+"/d.sock"; os.chdir("/ctr")
def switch(*a):
    r=sp.run([BIN,"kwin-capture",*a],capture_output=True,text=True,timeout=60)
    print(LABEL,"kwin-capture",*a,"rc",r.returncode,(r.stdout+r.stderr).strip()[:220].replace(chr(10)," / "),flush=True)
if os.environ.get("KWIN_SWITCH"): switch(*os.environ["KWIN_SWITCH"].split())
D=sp.Popen([BIN,"serve","--socket",SOCK,"--pid-file",R+"/d.pid"],stdout=open(R+"/d.log","w"),stderr=sp.STDOUT)
for _ in range(300):
    if os.path.exists(SOCK): break
    time.sleep(.1)
time.sleep(.3)
def call(t,a,to=70):
    a=dict(a);a.setdefault("session","e");r=sp.run([BIN,"call","--socket",SOCK,t,json.dumps(a)],capture_output=True,text=True,timeout=to)
    return json.loads(r.stdout) if r.stdout.lstrip().startswith("{") else {"_raw":(r.stdout+r.stderr)[:260]}
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
                            print(f"  [portal dialog: clicked {n.get_name()}]",flush=True); n.get_action_iface().do_action(0); time.sleep(1)
        except Exception: pass
threading.Thread(target=approve,daemon=True).start()
if MODE=="altgr":
    # Ground truth is the field's own contents: text can arrive through the input method, with no key presses at all.
    open(R+"/w.py","w").write('''import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QLineEdit(); w.setWindowTitle("Target"); w.resize(600,100)
w.textChanged.connect(lambda t:open(sys.argv[1],"w").write(t)); w.show(); a.exec()
''')
    L=R+"/k.log"; open(L,"w"); T=sp.Popen([sys.executable,R+"/w.py",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.5)
    cases=["plain ascii 123","ñandú ¿qué? €5","áéíóú ÁÉÍ ñÑ","¡hola! ¿sí? €","日本語","abc日def"]
    for t in cases:
        before=open(L,encoding="utf-8").read(); r=call("type_text",{"scope":"desktop","text":t}); time.sleep(1.2)
        now=open(L,encoding="utf-8").read(); got=now[len(before):]
        print(f"{LABEL:7}{t!r:22} got={got!r:22} {'exact' if got==t else 'WRONG'} effect={r.get('effect')} err={str(r.get('_raw') or '')[:110]}",flush=True)
    T.terminate()
elif MODE=="typeroute":
    # type_text at the desktop scope into targets that do and do not support the input method. Ground truth is what each target received.
    src={"Qt field":'''import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QLineEdit(); w.setWindowTitle("Target"); w.resize(600,100)
w.textChanged.connect(lambda t:open(sys.argv[1],"w").write(t)); w.show(); a.exec()
''',"Qt keys only":'''import sys
from PyQt6 import QtWidgets,QtCore
got=[]
class W(QtWidgets.QWidget):
    def keyPressEvent(self,e):
        if e.text(): got.append(e.text()); open(sys.argv[1],"w").write("".join(got))
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle("Target"); w.resize(600,100); w.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus); w.show(); a.exec()
''',"GTK3 field":'''import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
w=Gtk.Window(title="Target");e=Gtk.Entry();w.add(e);e.connect("changed",lambda x:open(sys.argv[1],"w").write(e.get_text()));w.connect("destroy",Gtk.main_quit);w.show_all();Gtk.main()
''',"GTK4 field":'''import gi,sys
gi.require_version("Gtk","4.0")
from gi.repository import Gtk,GLib
w=Gtk.Window(title="Target");e=Gtk.Entry();w.set_child(e);e.connect("changed",lambda x:open(sys.argv[1],"w").write(e.get_text()));w.present();GLib.MainLoop().run()
'''}
    for name,code in src.items():
        app=R+"/t.py"; L=R+"/t.log"; open(app,"w").write(code); open(L,"w").close()
        T=sp.Popen([sys.executable,app,L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.5)
        for t in ("plain ascii 123","ñandú €5"):
            before=open(L,encoding="utf-8").read(); r=call("type_text",{"scope":"desktop","text":t}); time.sleep(1.2)
            got=open(L,encoding="utf-8").read()[len(before):]
            print(f"{LABEL:6}{name:13}{t!r:19} got={got!r:19} {'exact' if got==t else 'LOST' if not got else 'WRONG'} effect={r.get('effect')} route={r.get('route')} err={str(r.get('_raw') or '')[:80]}",flush=True)
        T.terminate(); time.sleep(.5)
elif MODE=="frame":
    open(R+"/w.py","w").write('''import json,sys
from PyQt6 import QtWidgets,QtGui,QtCore
log=open(sys.argv[1],"a",buffering=1)
class C(QtWidgets.QWidget):
    def paintEvent(self,_):
        p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor("#202020")); p.fillRect(300,200,40,40,QtGui.QColor(255,0,255))
    def mousePressEvent(self,e):
        log.write(json.dumps([e.position().x(),e.position().y()])+"\\n")
a=QtWidgets.QApplication(sys.argv); w=C(); w.setWindowTitle("Target"); w.resize(700,500); w.show(); a.exec()
''')
    L=R+"/c.log"; open(L,"w"); T=sp.Popen([sys.executable,R+"/w.py",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.5)
    from PIL import Image
    print(LABEL,"get_screen_size:",json.dumps(call("get_screen_size",{}))[:300],flush=True)
    png=R+"/d.png"; s=call("get_desktop_state",{"screenshot_out_file":png}); print(LABEL,"desktop state keys:",{k:s[k] for k in s if k in("width","height","screenshot_width","screenshot_height","_raw","error")},flush=True)
    if os.path.exists(png):
        im=Image.open(png).convert("RGB"); W,H=im.size; xs=[];ys=[]
        px=im.load()
        for y in range(H):
            for x in range(W):
                r,g,b=px[x,y]
                if r>240 and g<20 and b>240: xs.append(x);ys.append(y)
        print(LABEL,"screenshot",(W,H),"marker px",len(xs),(min(xs),max(xs),min(ys),max(ys)) if xs else None,flush=True)
        if xs:
            cx,cy=(min(xs)+max(xs))//2,(min(ys)+max(ys))//2
            r=call("click",{"target":{"kind":"desktop","display_id":"primary"},"x":cx,"y":cy}); time.sleep(1)
            ev=[json.loads(l) for l in open(L)]
            hit=ev and 300<=ev[-1][0]<340 and 200<=ev[-1][1]<240
            print(f"{LABEL} clicked screenshot point {(cx,cy)}: window got {ev[-1] if ev else None} marker is x300-340 y200-240 => {'ON TARGET' if hit else 'MISSED'} effect={r.get('effect')} {str(r.get('_raw') or '')[:120]}",flush=True)
    T.terminate()
elif MODE=="rawinput":
    # Every raw input tool, aimed at a covered KWin window. KWin input is focus-bound, so each must refuse and deliver nothing.
    open(R+"/w.py","w").write('''import sys
from PyQt6 import QtWidgets,QtGui,QtCore
name,color,log=sys.argv[1:4]; log=open(log,"a",buffering=1)
class W(QtWidgets.QWidget):
    def paintEvent(self,_):
        QtGui.QPainter(self).fillRect(self.rect(),QtGui.QColor(color))
    def mousePressEvent(self,e): log.write("press %s btn=%s\\n"%(name,e.button().value))
    def wheelEvent(self,e): log.write("wheel %s\\n"%name)
    def keyPressEvent(self,e): log.write("key %s\\n"%name)
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle(name); w.resize(600,400); w.show(); a.exec()
''')
    L=R+"/l.log"; open(L,"w")
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA","#00ff00",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB","#ff0000",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    # Open the portal's input session first through the desktop route, so a refusal can't just mean "no session".
    r=call("click",{"target":{"kind":"desktop","display_id":"primary"},"x":300,"y":300}); time.sleep(1.5)
    print(LABEL,"portal session:",str(r.get("_raw") or r.get("effect"))[:80],flush=True)
    wa=(call("list_windows",{"pid":A.pid}).get("windows") or [{}])[0]; base={"pid":A.pid,"window_id":wa.get("window_id")}
    tests=[("press_key",{"key":"a"}),("type_text",{"text":"a"}),("click",{"x":300,"y":300}),("right_click",{"x":300,"y":300}),("double_click",{"x":300,"y":300}),("scroll",{"x":300,"y":300,"direction":"down","amount":1}),("hotkey",{"keys":["ctrl","a"]}),("type_text_chars",{"text":"a"}),("drag",{"from_x":300,"from_y":300,"to_x":320,"to_y":320})]
    ok=0
    for t,a in tests:
        call("get_window_state",{**base,"screenshot_out_file":R+"/ctx.png","include_accessibility_tree":False}); kw("activate","CapB"); time.sleep(.4); n0=os.path.getsize(L)
        r=call(t,{**base,**a,"delivery_mode":"foreground"}); time.sleep(.6)
        got=[g for g in open(L).read()[n0:].split("\n") if g]; active=kw("find","CapA")["active"]; reply=str(r.get("code") or r.get("_raw") or r.get("effect") or list(r)[:4])
        good=not got and not active and "foreground_unavailable" in reply; ok+=good
        print(f"{LABEL} {'PASS' if good else 'FAIL'} {t:16} delivered={got[:3]} covered_window_activated={active} reply={reply[:90]}",flush=True)
    f=call("bring_to_front",base); time.sleep(.4); g=kw("find","CapA")["active"]; ok+=bool(g)
    print(f"{LABEL} {'PASS' if g else 'FAIL'} bring_to_front still activates the exact window | {str(f.get('_raw') or 'ok')[:90]}",flush=True)
    print(f"{LABEL} RESULT {ok}/{len(tests)+1}",flush=True)
    A.terminate();Bw.terminate()
elif MODE=="capture":
    from PIL import Image
    open(R+"/w.py","w").write('''import sys
from PyQt6 import QtWidgets,QtGui,QtCore
name,color,log=sys.argv[1:4]; log=open(log,"a",buffering=1)
class W(QtWidgets.QWidget):
    def paintEvent(self,_):
        QtGui.QPainter(self).fillRect(self.rect(),QtGui.QColor(color))
    def mousePressEvent(self,e): log.write("press %s\\n"%name)
    def keyPressEvent(self,e): log.write("key %s\\n"%name)
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle(name); w.resize(600,400)
b=QtWidgets.QPushButton("Hit",w); b.setAccessibleName("Hit"+name); b.move(20,20); b.clicked.connect(lambda:log.write("clicked %s\\n"%name)); w.show(); a.exec()
''')
    L=R+"/l.log"; open(L,"w")
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA","#00ff00",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB","#ff0000",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    ok=[]
    def check(n,v,d=""):
        ok.append(bool(v)); print(f"{LABEL:8}{'PASS' if v else 'FAIL'} {n} | {str(d)[:125]}",flush=True)
    la=call("list_windows",{"pid":A.pid}).get("windows") or []; lb=call("list_windows",{"pid":Bw.pid}).get("windows") or []
    check("list finds both windows",bool(la and lb),(la[:1] or call("list_windows",{"pid":A.pid})))
    if la and lb:
        wa,wb=la[0],lb[0]; g=kw("find","CapA")
        b=wa["bounds"]; check("bounds match KWin",[b["x"],b["y"],b["width"],b["height"]]==[round(v) for v in g["frame"]],(b,g["frame"]))
        check("pid is the real owner",wa.get("pid")==A.pid and wb.get("pid")==Bw.pid,(wa.get("pid"),A.pid))
        check("covered window is below",(wa.get("z_index") is not None and wb.get("z_index") is not None and wa["z_index"]<wb["z_index"]),(wa.get("z_index"),wb.get("z_index")))
        def color(pid,wid,name):
            p=R+"/"+name+".png"
            if os.path.exists(p): os.remove(p)
            t0=time.monotonic(); s=call("get_window_state",{"pid":pid,"window_id":wid,"include_accessibility_tree":False,"screenshot_out_file":p}); ms=round((time.monotonic()-t0)*1e3)
            if not os.path.exists(p): return None,None,str(s.get("_raw") or s.get("degraded_reason") or s)[:110],ms
            im=Image.open(p).convert("RGB"); return im.size,im.getpixel((im.size[0]-10,im.size[1]-10)),"",ms
        size,px,err,ms=color(A.pid,wa["window_id"],"a"); check("capture of a COVERED window shows that window (green)",px and px[1]>200 and px[0]<60,(size,px,err,f"{ms}ms"))
        check("capture size matches the window's logical frame",size==(round(g["frame"][2]),round(g["frame"][3])),(size,g["frame"]))
        size,px,err,ms=color(Bw.pid,wb["window_id"],"b"); check("capture of the front window shows it (red)",px and px[0]>200 and px[1]<60,(size,px,err,f"{ms}ms"))
        f=call("bring_to_front",{"pid":A.pid,"window_id":wa["window_id"]}); time.sleep(.4); g=kw("find","CapA")
        check("bring_to_front makes the exact window active",g["active"],(str(f.get("_raw") or "ok")[:110],g["active"]))
        la2=call("list_windows",{"pid":A.pid}).get("windows") or [{}]; lb2=call("list_windows",{"pid":Bw.pid}).get("windows") or [{}]
        check("stacking follows",(la2[0].get("z_index") or 0)>(lb2[0].get("z_index") or 0),(la2[0].get("z_index"),lb2[0].get("z_index")))
        kw("activate","CapB"); time.sleep(.3)
        s=call("get_window_state",{"pid":A.pid,"window_id":wa["window_id"],"include_screenshot":False}); pass
        import re
        m=re.search(r'\[(\d+)\][^\n]*"HitCapA"',s.get("tree_markdown") or "")
        check("tree of a covered window",bool(m),str(s.get("tree_markdown") or s.get("degraded_reason") or s.get("_raw"))[:110])
        if m:
            n0=os.path.getsize(L); r=call("click",{"pid":A.pid,"window_id":wa["window_id"],"element_token":f"{s['snapshot_id']}:{m.group(1)}"}); time.sleep(.4)
            got=open(L).read()[n0:]; check("click by element reaches the covered window, not the front one","clicked CapA" in got and "CapB" not in got,(got.strip(),r.get("effect")))
        kw("activate","CapB"); time.sleep(.3)
        n0=os.path.getsize(L)
        r1=call("press_key",{"pid":A.pid,"window_id":wa["window_id"],"key":"a","delivery_mode":"foreground"}); r2=call("click",{"pid":A.pid,"window_id":wa["window_id"],"x":300,"y":300}); time.sleep(.5)
        got=open(L).read()[n0:]
        check("raw window-scoped key and pointer refused, nothing delivered",got=="" and "foreground_unavailable" in str(r1.get("_raw")) and r2.get("code")=="background_unavailable",(str(r1.get("_raw"))[:40],r2.get("code"),repr(got)))
    print(f"{LABEL} RESULT {sum(ok)}/{len(ok)}",flush=True)
    A.terminate();Bw.terminate()
elif MODE=="switch":
    # The operator's switch against a running daemon: off, on, Deny, override, off again. No restart anywhere. Real permission checks.
    import dbus
    from PIL import Image
    open(R+"/w.py","w").write('''import sys
from PyQt6 import QtWidgets,QtGui
name,color=sys.argv[1:3]
class W(QtWidgets.QWidget):
    def paintEvent(self,_): QtGui.QPainter(self).fillRect(self.rect(),QtGui.QColor(color))
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle(name); w.resize(600,400); w.show(); a.exec()
''')
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA","#00ff00"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB","#ff0000"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    ok=[]
    def check(n,v,d=""):
        ok.append(bool(v)); print(f"{LABEL} {'PASS' if v else 'FAIL'} {n} | {str(d)[:170]}",flush=True)
    ENTRY=os.environ["XDG_DATA_HOME"]+"/applications/ai.cua.driver.desktop"
    def lst():
        l=call("list_windows",{"pid":A.pid}).get("windows") or [{}]; return l[0]
    def isk(w): return w.get("z_index") is not None and w.get("bounds",{}).get("width")==round(kw("find","CapA")["frame"][2]) and w.get("bounds",{}).get("x")==round(kw("find","CapA")["frame"][0])
    def shot(wid):
        p=R+"/s.png"
        if os.path.exists(p): os.remove(p)
        s=call("get_window_state",{"pid":A.pid,"window_id":wid,"include_accessibility_tree":False,"screenshot_out_file":p})
        if not os.path.exists(p): return None,str(s.get("_raw") or s.get("code") or s.get("screenshot_error") or s.get("degraded_reason") or list(s))[:130]
        im=Image.open(p).convert("RGB"); return im.getpixel((im.size[0]-10,im.size[1]-10)),str(s.get("screenshot_frame_valid"))
    green=lambda px: px and px[1]>200 and px[0]<60
    w0=lst(); print(LABEL,"off window",w0,flush=True)
    check("off: not on the KWin adapter",not isk(w0),{k:w0.get(k) for k in("window_id","z_index","bounds")})
    px,d=shot(w0.get("window_id")); check("off: no exact capture of the covered window",not green(px),(px,d))
    check("off: no entry written",not os.path.exists(ENTRY))
    switch("status"); t0=time.monotonic(); switch("on"); on_ms=round((time.monotonic()-t0)*1e3)
    check("on: entry written, or none needed",True,(os.path.exists(ENTRY),f"{on_ms}ms"))
    tries=0; w=lst()
    while not isk(w) and tries<40: tries+=1; time.sleep(.25); w=lst()
    check("on: adapter answers without a restart",isk(w),f"{tries} extra list calls, {tries*.25}s; {w.get('window_id')}")
    if isk(w):
        kid=w["window_id"]; px,d=shot(kid); check("on: capture of the COVERED window is that window",green(px),(px,d))
        f=call("bring_to_front",{"pid":A.pid,"window_id":kid}); time.sleep(.4); check("on: bring_to_front raises it",kw("find","CapA")["active"],str(f.get("_raw") or "ok")[:90]); kw("activate","CapB"); time.sleep(.3)
        bus=dbus.SessionBus(); store=dbus.Interface(bus.get_object("org.freedesktop.impl.portal.PermissionStore","/org/freedesktop/impl/portal/PermissionStore"),"org.freedesktop.impl.portal.PermissionStore")
        store.SetPermission("screenshot",True,"screenshot","",["no"]); time.sleep(1.3)
        w2=lst(); check("Deny: adapter off on the next calls",not isk(w2),w2.get("window_id"))
        px,d=shot(kid); check("Deny: old KWin id gives no capture",not green(px),(px,d)); switch("status")
        switch("on","--override-portal-deny"); time.sleep(1.3); t=0; w3=lst()
        while not isk(w3) and t<40: t+=1; time.sleep(.25); w3=lst()
        check("override: back on",isk(w3),f"{t} extra list calls")
        px,d=shot(w3.get("window_id")); check("override: captures the covered window despite Deny",green(px),(px,d))
        store.DeletePermission("screenshot","screenshot","")
        switch("off"); time.sleep(.1); w4=lst(); check("off again: adapter off on the next call",not isk(w4),w4.get("window_id"))
        check("off again: entry removed",not os.path.exists(ENTRY))
        px,d=shot(w3.get("window_id")); check("off again: old KWin id gives no capture",not green(px),(px,d))
    print(f"{LABEL} RESULT {sum(ok)}/{len(ok)}",flush=True)
    A.terminate();Bw.terminate()
elif MODE=="typeswitch":
    # Desktop typing with the capture switch off, on and off again, for what PR 6827's keystate rule does with no entry. Ground truth is the field.
    open(R+"/w.py","w").write('''import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv); e=QtWidgets.QLineEdit(); e.setWindowTitle("TypeW"); e.resize(500,60)
e.textChanged.connect(lambda t:open(sys.argv[1],"w").write(t)); e.show(); e.setFocus(); a.exec()
''')
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    out=R+"/o.txt"; open(out,"w").close(); P=sp.Popen([sys.executable,R+"/w.py",out],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2); kw("activate","TypeW"); time.sleep(.5)
    def ty(tag):
        for text in ("abc","123"):
            open(out,"w").close(); kw("activate","TypeW"); time.sleep(.2)
            before=open(out).read()
            r=call("type_text",{"scope":"desktop","text":text}); time.sleep(1.2); got=open(out).read()
            print(f"{LABEL} {tag} text={text!r} field={got!r} reply={str(r.get('code') or r.get('_raw') or r.get('effect'))[:170]}",flush=True)
    ty("off"); switch("on"); time.sleep(1); ty("on"); switch("off"); time.sleep(1); ty("off-again")
    P.terminate()
elif MODE=="grantprobe":
    # Does KWin let an executable with no grant capture? Probed from plain python3 (no .desktop entry names it), then through the driver.
    import dbus
    bus=dbus.SessionBus(); kp=sp.run(["pgrep","-x","kwin_wayland"],capture_output=True,text=True).stdout.split()
    env=open(f"/proc/{kp[0]}/environ").read() if kp else ""
    print(LABEL,"kwin pid",kp,"no-check env in kwin:",[e for e in env.split("\0") if "NO_PERMISSION" in e],flush=True)
    print(LABEL,"kwin version:",sp.run(["kwin_wayland","--version"],capture_output=True,text=True).stdout.strip(),flush=True)
    print(LABEL,"entries naming ScreenShot2:",sp.run("grep -rl 'org.kde.KWin.ScreenShot2' /usr/share/applications $XDG_DATA_HOME/applications 2>/dev/null | head -20",shell=True,capture_output=True,text=True).stdout.split(),flush=True)
    def direct(method,*args):
        r,w=os.pipe()
        try:
            o=dbus.Interface(bus.get_object("org.kde.KWin","/org/kde/KWin/ScreenShot2"),"org.kde.KWin.ScreenShot2")
            res=getattr(o,method)(*args,dbus.Dictionary({"native-resolution":False},signature="sv"),dbus.types.UnixFd(w))
            return "ALLOWED "+str({k:str(v) for k,v in res.items() if k in("width","height","type")})
        except dbus.DBusException as e: return "REFUSED "+e.get_dbus_name()+": "+e.get_dbus_message()[:110]
        finally: os.close(w);os.close(r)
    print(LABEL,"python3 CaptureWorkspace:",direct("CaptureWorkspace"),flush=True)
    open(R+"/w.py","w").write("""import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QWidget(); w.setWindowTitle("ProbeW"); w.resize(300,200); w.show(); a.exec()
""")
    W=sp.Popen([sys.executable,R+"/w.py"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    print(LABEL,"python3 CaptureActiveScreen:",direct("CaptureActiveScreen"),flush=True)
    l=(call("list_windows",{"pid":W.pid}).get("windows") or [{}])[0]
    print(LABEL,"driver list_windows:",{k:l.get(k) for k in("window_id","bounds","z_index")},flush=True)
    png=R+"/d.png"
    for i in range(3):
        if os.path.exists(png): os.remove(png)
        t0=time.monotonic(); s=call("get_desktop_state",{"screenshot_out_file":png}); ms=(time.monotonic()-t0)*1e3
        print(LABEL,f"driver get_desktop_state #{i}: {ms:.0f} ms file={os.path.exists(png)} {str(s.get('_raw') or '')[:100]}",flush=True)
    W.terminate()
    print(LABEL,"driver log kwin lines:",sp.run(["grep","-i","-c","kwin",R+"/d.log"],capture_output=True,text=True).stdout.strip(),flush=True)
elif MODE=="rawplus":
    # The tools rawinput doesn't cover, with no portal session opened first: refused, nothing delivered, and does a refused call raise a consent dialog?
    open(R+"/w.py","w").write("""import sys
from PyQt6 import QtWidgets,QtGui
name,color,log=sys.argv[1:4]; log=open(log,"a",buffering=1)
class W(QtWidgets.QWidget):
    def paintEvent(self,_): QtGui.QPainter(self).fillRect(self.rect(),QtGui.QColor(color))
    def mousePressEvent(self,e): log.write("press %s\\n"%name)
    def wheelEvent(self,e): log.write("wheel %s\\n"%name)
    def keyPressEvent(self,e): log.write("key %s\\n"%name)
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle(name); w.resize(600,400); w.show(); a.exec()
""")
    L=R+"/l.log"; open(L,"w")
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA","#00ff00",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB","#ff0000",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    wa=(call("list_windows",{"pid":A.pid}).get("windows") or [{}])[0]; base={"pid":A.pid,"window_id":wa.get("window_id")}
    for t,a in [("right_click",{"x":300,"y":300}),("scroll",{"x":300,"y":300,"direction":"down","amount":1}),("drag",{"from_x":300,"from_y":300,"to_x":320,"to_y":320}),("mouse_button_down",{"x":300,"y":300}),("mouse_button_up",{"x":300,"y":300}),("hotkey",{"keys":["ctrl","a"]})]:
        call("get_window_state",{**base,"screenshot_out_file":R+"/ctx.png","include_accessibility_tree":False}); kw("activate","CapB"); time.sleep(.3); n0=os.path.getsize(L); t0=time.monotonic()
        r=call(t,{**base,**a,"delivery_mode":"foreground"}); ms=(time.monotonic()-t0)*1e3; time.sleep(.5)
        got=[g for g in open(L).read()[n0:].split("\n") if g]; active=kw("find","CapA")["active"]
        print(f"{LABEL} {t:18} {ms:6.0f} ms delivered={got[:3]} activated={active} reply={str(r.get('code') or r.get('_raw') or r.get('effect') or list(r)[:4])[:120]}",flush=True)
    A.terminate();Bw.terminate()
elif MODE=="menu":
    # invoke_menu and bring_to_front on a covered window: both legitimate, both must still work.
    open(R+"/w.py","w").write("""import sys,gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
name,log=sys.argv[1:3]; log=open(log,"a",buffering=1)
w=Gtk.Window(title=name); w.set_default_size(600,400); b=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); mb=Gtk.MenuBar(); fi=Gtk.MenuItem(label="File"); m=Gtk.Menu(); fi.set_submenu(m); p=Gtk.MenuItem(label="Probe"); p.connect("activate",lambda *_: log.write("fired %s\\n"%name)); m.append(p); mb.append(fi); b.pack_start(mb,False,False,0); w.add(b); w.show_all(); Gtk.main()
""")
    L=R+"/l.log"; open(L,"w")
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL,env=dict(os.environ,GDK_BACKEND="wayland")); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL,env=dict(os.environ,GDK_BACKEND="wayland")); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    wa=(call("list_windows",{"pid":A.pid}).get("windows") or [{}])[0]; print(LABEL,"window",wa.get("window_id"),flush=True)
    r=call("invoke_menu",{"pid":A.pid,"window_id":wa.get("window_id"),"path":["File","Probe"]}); time.sleep(.8)
    print(LABEL,"invoke_menu: log",open(L).read().strip().split("\n"),"active",kw("find","CapA")["active"],"reply",str(r.get("_raw") or r.get("code") or r.get("effect") or "ok")[:140],flush=True)
    r=call("invoke_menu",{"pid":Bw.pid,"window_id":wa.get("window_id"),"path":["File","Probe"]})
    print(LABEL,"invoke_menu wrong pid:",str(r.get("_raw") or r.get("code") or r)[:120],flush=True)
    kw("activate","CapB"); time.sleep(.3)
    r=call("bring_to_front",{"pid":Bw.pid,"window_id":wa.get("window_id")}); time.sleep(.3)
    print(LABEL,"bring_to_front wrong pid:",str(r.get("_raw") or r)[:130],"active",kw("find","CapA")["active"],flush=True)
    r=call("bring_to_front",{"pid":A.pid,"window_id":wa.get("window_id")}); time.sleep(.3)
    print(LABEL,"bring_to_front:",str(r.get("_raw") or "ok")[:100],"active",kw("find","CapA")["active"],flush=True)
    A.terminate();Bw.terminate()
elif MODE=="popup":
    # An XWayland app's open context menu on KWin: a pid-only get_window_state must return the popup. Needs XWAYLAND=1.
    open(R+"/w.py","w").write("""import sys
from PyQt6 import QtWidgets,QtGui,QtCore
a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QWidget(); w.setWindowTitle("PopW"); w.resize(600,400); w.show()
m=QtWidgets.QMenu(w); m.addAction("One"); m.addAction("Two"); QtCore.QTimer.singleShot(1500,lambda: m.popup(w.mapToGlobal(QtCore.QPoint(50,50)))); a.exec()
""")
    env=dict(os.environ,QT_QPA_PLATFORM="xcb")
    W=sp.Popen([sys.executable,R+"/w.py"],stdout=sp.DEVNULL,stderr=sp.DEVNULL,env=env); time.sleep(4)
    l=call("list_windows",{"pid":W.pid}).get("windows") or []
    print(LABEL,"listed",[(x.get("window_id"),x.get("title")) for x in l],flush=True)
    s=call("get_window_state",{"pid":W.pid,"include_screenshot":False})
    print(LABEL,"pid-only chose",s.get("window_id"),"popup flag",s.get("popup"),"title",s.get("window_title"),str(s.get("_raw") or "")[:120],flush=True)
    print(LABEL,"RESULT", "POPUP" if s.get("popup") else "NOT-POPUP",flush=True)
    W.terminate()
elif MODE=="resizerace":
    # A window resizing itself while it's captured. A 100 px band at its left edge shows any stretch: its width in the image should stay 100 (times the image's scale).
    from PIL import Image
    open(R+"/w.py","w").write("""import sys
from PyQt6 import QtWidgets,QtGui,QtCore
class W(QtWidgets.QWidget):
    def paintEvent(self,_):
        p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor("#ffffff")); p.fillRect(0,0,100,self.height(),QtGui.QColor("#000000"))
a=QtWidgets.QApplication(sys.argv); w=W(); w.setWindowTitle("RaceW"); w.resize(600,400); w.show()
st=[0]
def flip():
    st[0]^=1; w.resize(*((700,500) if st[0] else (500,340)))
t=QtCore.QTimer(); t.timeout.connect(flip); t.start(int(sys.argv[1])); a.exec()
""")
    W=sp.Popen([sys.executable,R+"/w.py",os.environ.get("FLIP_MS","12")],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    wa=(call("list_windows",{"pid":W.pid}).get("windows") or [{}])[0]; p=R+"/r.png"; n=int(os.environ.get("N","60")); bands=[]; sizes={}; fails=0
    for i in range(n):
        if os.path.exists(p): os.remove(p)
        s=call("get_window_state",{"pid":W.pid,"window_id":wa.get("window_id"),"include_accessibility_tree":False,"screenshot_out_file":p,"max_image_dimension":0})
        if not os.path.exists(p): fails+=1; err=str(s.get("_raw") or s.get("screenshot_error") or s)[:100]; continue
        im=Image.open(p).convert("L"); w,h=im.size; sizes[(w,h)]=sizes.get((w,h),0)+1
        y=h-20; b=0
        for x in range(w):
            if im.getpixel((x,y))<80: b+=1
        bands.append(b)
    off=[b for b in bands if abs(b-100)>3]
    print(LABEL,f"captures {len(bands)} failed {fails} band widths min {min(bands) if bands else 0} max {max(bands) if bands else 0} stretched(|band-100|>3): {len(off)} sizes {len(sizes)} sample {sorted(set(off))[:12]}",flush=True)
    W.terminate()
elif MODE=="scaleprobe":
    # What ScreenShot2 reports for a window: pixels, scale. Permission checks off.
    import dbus
    from PIL import Image
    open(R+"/w.py","w").write("""import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QWidget(); w.setWindowTitle("ScaleW"); w.resize(801,601); w.show(); a.exec()
""")
    W=sp.Popen([sys.executable,R+"/w.py"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2)
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    for size in [(801,601),(801,720),(800,720),(803,607)]:
        kw("frame","ScaleW",50,50,*size); time.sleep(.6); g=kw("find","ScaleW")
        bus=dbus.SessionBus(); o=dbus.Interface(bus.get_object("org.kde.KWin","/org/kde/KWin/ScreenShot2"),"org.kde.KWin.ScreenShot2")
        r,w=os.pipe(); res=o.CaptureWindow(g["id"],dbus.Dictionary({"native-resolution":False,"include-decoration":True,"include-shadow":False},signature="sv"),dbus.types.UnixFd(w)); os.close(w); os.close(r)
        print(LABEL,"frame",g["frame"],"image",int(res["width"]),int(res["height"]),"scale",float(res["scale"]),"image/scale",float(res["width"])/float(res["scale"]),float(res["height"])/float(res["scale"]),flush=True)
    W.terminate()
elif MODE=="rawelem":
    # Element tokens on a control with no semantic action, covered KWin window, every delivery: refused with the exact code, nothing delivered, no X11 path. Works with and without XWAYLAND=1.
    open(R+"/w.py","w").write("""import sys,gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
name,log=sys.argv[1:3]; log=open(log,"a",buffering=1)
w=Gtk.Window(title=name); w.set_default_size(600,400); t=Gtk.TextView(); t.get_buffer().set_text("no semantic action")
t.connect("button-press-event",lambda *_: log.write("press %s\\n"%name) and False); t.connect("scroll-event",lambda *_: log.write("scroll %s\\n"%name) and False); w.add(t); w.show_all(); Gtk.main()
""")
    L=R+"/l.log"; open(L,"w"); env=dict(os.environ,GDK_BACKEND="wayland")
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    A=sp.Popen([sys.executable,R+"/w.py","CapA",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL,env=env); time.sleep(2)
    Bw=sp.Popen([sys.executable,R+"/w.py","CapB",L],stdout=sp.DEVNULL,stderr=sp.DEVNULL,env=env); time.sleep(2)
    kw("frame","CapA",100,100,600,400); kw("frame","CapB",100,100,600,400); kw("activate","CapB"); time.sleep(.5)
    wa=(call("list_windows",{"pid":A.pid}).get("windows") or [{}])[0]; base={"pid":A.pid,"window_id":wa.get("window_id")}
    import re
    bad=0
    for t,a in [("click",{}),("right_click",{}),("double_click",{}),("scroll",{"direction":"down","amount":1})]:
        for d in ("background","foreground"):
            s=call("get_window_state",{**base,"include_screenshot":False}); kw("activate","CapB"); time.sleep(.3)
            m=re.search(r"\[(\d+)\] text",s.get("tree_markdown") or "")
            if not m: print(LABEL,"no row",str(s.get("tree_markdown"))[:200],flush=True); break
            n0=os.path.getsize(L); r=call(t,{**base,**a,"delivery_mode":d,"element_token":f"{s['snapshot_id']}:{m.group(1)}"}); time.sleep(.4)
            got=[g for g in open(L).read()[n0:].split("\n") if g]; active=kw("find","CapA")["active"]; reply=str(r.get("code") or r.get("_raw") or r.get("effect") or list(r)[:4])
            want="background_unavailable" if d=="background" else "foreground_unavailable"; good=not got and not active and want in reply and "X11" not in str(r); bad+=not good
            print(f"{LABEL} {'PASS' if good else 'FAIL'} {t:12} {d:10} delivered={got[:2]} activated={active} reply={reply[:110]}",flush=True)
    print(LABEL,"driver alive",D.poll() is None,"RESULT fails",bad,flush=True)
    A.terminate();Bw.terminate()
elif MODE=="savedeny":
    # A Deny saved in the portal, then desktop screenshots. Which route answers? Portal route: refused, and no dialog. ScreenShot2 route: captured.
    import dbus
    from PIL import Image
    bus=dbus.SessionBus(); store=dbus.Interface(bus.get_object("org.freedesktop.impl.portal.PermissionStore","/org/freedesktop/impl/portal/PermissionStore"),"org.freedesktop.impl.portal.PermissionStore")
    store.SetPermission("screenshot",True,"screenshot","",["no"])
    print(LABEL,"saved:",str(store.Lookup("screenshot","screenshot"))[:120],flush=True)
    png=R+"/d.png"; n=int(os.environ.get("N","4")); ok=0
    for i in range(n):
        if os.path.exists(png): os.remove(png)
        t0=time.monotonic(); s=call("get_desktop_state",{"screenshot_out_file":png}); ms=(time.monotonic()-t0)*1e3; got=os.path.exists(png); ok+=got
        print(LABEL,f"#{i} {ms:.0f} ms file={got} {str(s.get('_raw') or s.get('screenshot_error') or s.get('code') or '')[:140]}",flush=True)
    print(LABEL,f"RESULT {ok}/{n} screenshots with Deny saved",flush=True)
elif MODE=="desktopspeed":
    from PIL import Image
    png=R+"/d.png"; times=[]; sizes=set(); dialogs_before=0
    for i in range(int(os.environ.get("N","21"))):
        if os.path.exists(png): os.remove(png)
        t0=time.monotonic(); s=call("get_desktop_state",{"screenshot_out_file":png}); ms=(time.monotonic()-t0)*1e3
        ok=os.path.exists(png)
        if ok: sizes.add(Image.open(png).size)
        if i==0: print(f"{LABEL} first call {ms:.0f} ms ok={ok} {str(s.get('_raw') or '')[:120]}",flush=True)
        else: times.append(ms if ok else None)
    good=sorted(t for t in times if t is not None)
    print(f"{LABEL} after first: ok {len(good)}/{len(times)} median {good[len(good)//2] if good else 0:.0f} ms min {good[0] if good else 0:.0f} max {good[-1] if good else 0:.0f} sizes {sizes}",flush=True)
elif MODE=="text":
    # type_text by element into the toolkit's own entry, on Wayland. Ground truth is the entry's changed signal.
    src={"GTK3":'''import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
w=Gtk.Window(title="probe");e=Gtk.Entry();e.set_text(sys.argv[2]);e.set_position(-1);e.get_accessible().set_name("Probe");w.add(e);w.connect("destroy",Gtk.main_quit)
out=lambda:open(sys.argv[1],"w").write(e.get_text());e.connect("changed",lambda x:out());out();w.show_all();Gtk.main()
''',"GTK4":'''import gi,sys
gi.require_version("Gtk","4.0")
from gi.repository import Gtk,GLib
w=Gtk.Window(title="probe");e=Gtk.Entry();e.set_text(sys.argv[2]);e.set_position(-1);e.update_property([Gtk.AccessibleProperty.LABEL],["Probe"]);w.set_child(e)
out=lambda:open(sys.argv[1],"w").write(e.get_text());e.connect("changed",lambda x:out());out();w.present();l=GLib.MainLoop();w.connect("close-request",lambda *a:l.quit());l.run()
''',"Qt":'''import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv);e=QtWidgets.QLineEdit(sys.argv[2]);e.setAccessibleName("Probe");e.setWindowTitle("probe")
out=lambda *x:open(sys.argv[1],"w").write(e.text());e.textChanged.connect(out);out();e.resize(400,60);e.show();a.exec()
''',"GTK3-TextView":'''import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
w=Gtk.Window(title="probe");e=Gtk.TextView();b=e.get_buffer();b.set_text(sys.argv[2]);b.place_cursor(b.get_end_iter());e.get_accessible().set_name("Probe");w.add(e);w.connect("destroy",Gtk.main_quit)
out=lambda:open(sys.argv[1],"w").write(b.get_text(b.get_start_iter(),b.get_end_iter(),True));b.connect("changed",lambda x:out());out();w.show_all();Gtk.main()
''',"GTK4-TextView":'''import gi,sys
gi.require_version("Gtk","4.0")
from gi.repository import Gtk,GLib
w=Gtk.Window(title="probe");e=Gtk.TextView();b=e.get_buffer();b.set_text(sys.argv[2]);b.place_cursor(b.get_end_iter());e.update_property([Gtk.AccessibleProperty.LABEL],["Probe"]);w.set_child(e)
out=lambda:open(sys.argv[1],"w").write(b.get_text(b.get_start_iter(),b.get_end_iter(),True));b.connect("changed",lambda x:out());out();w.present();l=GLib.MainLoop();w.connect("close-request",lambda *a:l.quit());l.run()
''',"Qt-PlainTextEdit":'''import sys
from PyQt6 import QtWidgets,QtGui
a=QtWidgets.QApplication(sys.argv);e=QtWidgets.QPlainTextEdit(sys.argv[2]);e.moveCursor(QtGui.QTextCursor.MoveOperation.End);e.setAccessibleName("Probe");e.setWindowTitle("probe")
out=lambda *x:open(sys.argv[1],"w").write(e.toPlainText());e.textChanged.connect(out);out();e.resize(400,160);e.show();a.exec()
'''}
    import re
    TEXTS=[("","ASCII-END"),("","✓ABC"),("","|ñ-END"),("","ñ🙂ab"),("","日本語 🙂 end"),("pre ","✓ABC"),("pre ","|ñ-END"),("pre ","ñ🙂ab")]
    for tk,code in src.items():
        app=R+"/"+tk+".py"; open(app,"w").write(code); good=tot=0; said=False
        for start,text in TEXTS:
            out=R+"/o.txt"; p=sp.Popen([sys.executable,app,out,start],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.2)
            try:
                wins=call("list_windows",{"pid":p.pid}).get("windows") or []
                a={"pid":p.pid,"query":"Probe","include_screenshot":False}
                if wins: a["window_id"]=wins[0]["window_id"]
                s=call("get_window_state",a); m=re.search(r'\[(\d+)\][^\n]*"Probe"',s.get("tree_markdown") or "")
                tot+=1
                if not m:
                    if not said: print(LABEL,tk,"no row:",str(s.get("degraded_reason") or s.get("_raw") or s)[:170],flush=True); said=True
                    continue
                r=call("type_text",{"pid":p.pid,"window_id":s["window_id"],"element_token":f'{s["snapshot_id"]}:{m.group(1)}',"text":text}); time.sleep(.4)
                got=open(out).read(); want=start+text; good+=got==want
                if got!=want: print(f"{LABEL} {tk:5}{start!r:7}{text!r:17} got={got!r} effect={r.get('effect')}",flush=True)
            finally: p.terminate(); time.sleep(.2)
        print(f"{LABEL} {tk}: {good}/{tot} exact",flush=True)
elif MODE=="textbig":
    # A focused field in an app whose tree outlasts the 1.5 s input budget: the walk spends it all, then the write still goes out.
    # type_text with no element, so the route is type_into_editable, which only X11 reaches: a second daemon sees only XWayland.
    # It starts after the field took focus, so the focus-event log has nothing and it has to walk. Ground truth is the field's own text.
    src={"Qt":("""import sys
from PyQt6 import QtWidgets
n=int(sys.argv[2]); a=QtWidgets.QApplication(sys.argv); w=QtWidgets.QWidget(); w.setWindowTitle("probe"); l=QtWidgets.QVBoxLayout(w)
e=QtWidgets.QLineEdit(); e.setAccessibleName("Probe"); l.addWidget(e); g=QtWidgets.QGridLayout(); l.addLayout(g)
for b in range(n//100):
    q=QtWidgets.QWidget(); h=QtWidgets.QGridLayout(q); g.addWidget(q,b//10,b%10)
    for i in range(100): h.addWidget(QtWidgets.QLabel("r%d"%i),i//10,i%10)
e.textChanged.connect(lambda t:open(sys.argv[1],"w").write(t)); w.show(); e.setFocus(); a.exec()
""",{"QT_QPA_PLATFORM":"xcb"}),"GTK3":("""import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
n=int(sys.argv[2]); w=Gtk.Window(title="probe"); l=Gtk.Box(orientation=Gtk.Orientation.VERTICAL); w.add(l); w.connect("destroy",Gtk.main_quit)
e=Gtk.Entry(); e.get_accessible().set_name("Probe"); l.add(e); g=Gtk.Grid(); l.add(g)
for b in range(n//100):
    q=Gtk.Grid(); g.attach(q,b%10,b//10,1,1)
    for i in range(100): q.attach(Gtk.Label(label="r%d"%i),i%10,i//10,1,1)
e.connect("changed",lambda x:open(sys.argv[1],"w").write(e.get_text())); w.show_all(); e.grab_focus(); Gtk.main()
""",{"GDK_BACKEND":"x11"})}
    SX=R+"/x.sock"; XE={k:v for k,v in os.environ.items() if k not in("WAYLAND_DISPLAY","CUA_DRIVER_RS_ENABLE_WAYLAND")}; XE["XDG_SESSION_TYPE"]="x11"
    def call(t,a,to=70):
        a=dict(a);a.setdefault("session","e");r=sp.run([BIN,"call","--socket",SX,t,json.dumps(a)],capture_output=True,text=True,timeout=to,env=XE)
        return json.loads(r.stdout) if r.stdout.lstrip().startswith("{") else {"_raw":(r.stdout+r.stderr)[:260]}
    out=R+"/o.txt"
    for tk,(code,env) in src.items():
        app=R+"/big"+tk+".py"; open(app,"w").write(code)
        for n in ((int(os.environ.get("BIG","6000")),) if os.environ.get("ONLYBIG") else (0,int(os.environ.get("BIG","6000")))):
            good=tot=0
            for text in (os.environ["BIGTEXTS"].split("|") if os.environ.get("BIGTEXTS") else ("ñ🙂ab","日本語 🙂 end","✓ABC")):
                open(out,"w").close(); p=sp.Popen([sys.executable,app,out,str(n)],env=dict(os.environ,**env),stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(3+n/1000)
                XD=sp.Popen([BIN,"serve","--socket",SX,"--pid-file",R+"/x.pid"],env=dict(XE,CUA_ATSPI_DEBUG="1"),stdout=open(R+"/x.log","w"),stderr=sp.STDOUT); time.sleep(1.5)
                try:
                    wins=call("list_windows",{"pid":p.pid}).get("windows") or []
                    ROUTE=os.environ.get("ROUTE",""); extra={"delivery_mode":os.environ["DELIVERY"]} if os.environ.get("DELIVERY") else {}
                    tok=None
                    if ROUTE and wins:
                        s=call("get_window_state",{"pid":p.pid,"window_id":wins[0]["window_id"],"query":"Probe","include_screenshot":False},to=120); import re as _re; m=_re.search(r'\[(\d+)\][^\n]*"Probe"',s.get("tree_markdown") or ""); tok=f'{s.get("snapshot_id")}:{m.group(1)}' if m else None
                        if not tok: print(LABEL,tk,"no token",str(s)[:200],flush=True)
                    t0=time.monotonic()
                    if not wins: r={"_raw":"no window"}
                    elif ROUTE=="setvalue": r=call("set_value",{"pid":p.pid,"window_id":wins[0]["window_id"],"element_token":tok,"value":text})
                    elif ROUTE=="element": r=call("type_text",dict({"pid":p.pid,"window_id":wins[0]["window_id"],"element_token":tok,"text":text},**extra))
                    else: r=call("type_text",dict({"pid":p.pid,"window_id":wins[0]["window_id"],"text":text},**extra))
                    ms=round((time.monotonic()-t0)*1e3); time.sleep(.5)
                    got=open(out,encoding="utf-8",errors="replace").read(); tot+=1; good+=got==text
                    walk=[l for l in open(R+"/x.log",errors="replace").read().splitlines() if "truncation=" in l or "budget" in l]
                    print(f"{LABEL} {tk:5}labels={n} {text!r:17} got={got!r} {'exact' if got==text else 'WRONG'} {ms}ms effect={r.get('effect')} {str(r.get('code') or r.get('_raw') or '')[:60]} budget_spent={any('budget exhausted' in l for l in walk)}",flush=True)
                finally:
                    p.terminate(); XD.terminate(); XD.wait(); time.sleep(.3)
                    if os.path.exists(SX): os.remove(SX)
            print(f"{LABEL} {tk} labels={n}: {good}/{tot} exact last={json.dumps(r,ensure_ascii=False)[:330]}",flush=True)
elif MODE=="gtk3row":
    # The repo's own GTK3 catalog rows, against a driver that sees only XWayland. The test binary and fixture sit next to the driver.
    XE={k:v for k,v in os.environ.items() if os.environ.get("LANE")=="wayland" or k not in("WAYLAND_DISPLAY","CUA_DRIVER_RS_ENABLE_WAYLAND")}; XE.update({} if os.environ.get("LANE")=="wayland" else dict(XDG_SESSION_TYPE="x11",GDK_BACKEND="x11")); XE.update(CUA_TEST_DRIVER_BIN=BIN,HARNESS_GTK3_EXE=os.path.dirname(BIN)+"/main.py",CUA_TEST_WORKSPACE_ROOT=R,RUST_BACKTRACE="0")
    for row in os.environ.get("ROWS","").split(","):
        r=sp.run([os.path.dirname(BIN)+"/harness_gtk3_test","--ignored","--exact",row,"--nocapture","--test-threads=1"],env=XE,capture_output=True,text=True,timeout=120,cwd=R)
        o=r.stdout+r.stderr; keep=[l for l in o.splitlines() if l.startswith("test result") or "panicked" in l or "mirror=" in l or "assert" in l.lower()]
        print(LABEL,row,"exit",r.returncode,keep[-4:],flush=True)
        if r.returncode: print(LABEL,"tail",o[-700:].replace("\n"," | "),flush=True)
elif MODE=="bridgefull":
    # Every toolkit with NO_AT_BRIDGE=1 and =0, on native Wayland (or on X11 with BACKEND=x11, a driver that sees only XWayland).
    # Ground truth for "joined" is the accessibility registry itself, read from this script, not from the driver.
    src={"GTK3":"""import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
w=Gtk.Window(title="probe");e=Gtk.Entry();e.get_accessible().set_name("Probe");w.add(e);w.connect("destroy",Gtk.main_quit);w.show_all();Gtk.main()
""","GTK4":"""import gi,sys
gi.require_version("Gtk","4.0")
from gi.repository import Gtk,GLib
w=Gtk.Window(title="probe");e=Gtk.Entry();e.update_property([Gtk.AccessibleProperty.LABEL],["Probe"]);w.set_child(e);w.present();GLib.MainLoop().run()
""","Qt":"""import sys
from PyQt6 import QtWidgets
a=QtWidgets.QApplication(sys.argv);e=QtWidgets.QLineEdit();e.setAccessibleName("Probe");e.setWindowTitle("probe");e.resize(400,60);e.show();a.exec()
"""}
    x11=os.environ.get("BACKEND")=="x11"; ENV={"GDK_BACKEND":"x11","QT_QPA_PLATFORM":"xcb"} if x11 else {}
    if x11:
        SX=R+"/x.sock"; XE={k:v for k,v in os.environ.items() if k not in("WAYLAND_DISPLAY","CUA_DRIVER_RS_ENABLE_WAYLAND")}; XE["XDG_SESSION_TYPE"]="x11"
        sp.Popen([BIN,"serve","--socket",SX,"--pid-file",R+"/x.pid"],env=XE,stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(1.5)
        def call(t,a,to=70):
            a=dict(a);a.setdefault("session","e");r=sp.run([BIN,"call","--socket",SX,t,json.dumps(a)],capture_output=True,text=True,timeout=to,env=XE)
            return json.loads(r.stdout) if r.stdout.lstrip().startswith("{") else {"_raw":(r.stdout+r.stderr)[:400]}
    def joined(pid):
        d=Atspi.get_desktop(0)
        return any((d.get_child_at_index(i) and d.get_child_at_index(i).get_process_id()==pid) for i in range(d.get_child_count()))
    short=lambda r:str(r.get("degraded_reason") or r.get("_raw") or r.get("code") or r.get("error") or "")[:int(os.environ.get("SHORT","170"))]
    for tk,code in src.items():
        app=R+"/"+tk+".py"; open(app,"w").write(code)
        for v in ("1","0"):
            p=sp.Popen([sys.executable,app],env=dict(os.environ,NO_AT_BRIDGE=v,**ENV),stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(3)
            lw=call("list_windows",{"pid":p.pid}); wins=lw.get("windows") or []
            print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} registry_joined={joined(p.pid)} list_windows={len(wins)} list_reason={str(lw.get('reason') or lw.get('degraded_reason') or '')[:150]!r}",flush=True)
            if not wins:
                allw=[w for w in (call("list_windows",{}).get("windows") or []) if w.get("title")=="probe"]
                raw=sp.run([BIN,"call","--socket",SOCK,"list_windows",json.dumps({"pid":p.pid,"session":"e"}),"--text"],capture_output=True,text=True).stdout if False else ""
                print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} unfiltered list has it: {[(w.get('window_id'),w.get('pid')) for w in allw]}",flush=True)
                if allw:
                    s=call("get_window_state",{"pid":p.pid,"window_id":allw[0]["window_id"],"query":"Probe","include_screenshot":False})
                    print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} that window_id tree={'Probe' in (s.get('tree_markdown') or '')} says={short(s)!r}",flush=True)
            s=call("get_window_state",{"pid":p.pid,"query":"Probe","include_screenshot":False})
            print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} pid-only     tree={'Probe' in (s.get('tree_markdown') or '')} says={short(s)!r}",flush=True)
            if wins:
                s=call("get_window_state",{"pid":p.pid,"window_id":wins[0]["window_id"],"query":"Probe","include_screenshot":False})
                print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} window_id    tree={'Probe' in (s.get('tree_markdown') or '')} says={short(s)!r}",flush=True)
            if tk=="GTK3" and os.environ.get("TOOLS"):
                for t,a in (("press_key",{"key":"a"}),("hotkey",{"keys":["ctrl","a"]}),("scroll",{"direction":"down","amount":1}),("type_text",{"text":"a"}),("type_text_chars",{"text":"a"})):
                    r=call(t,{"pid":p.pid,**a},20)
                    print(f"{LABEL} {tk:5}NO_AT_BRIDGE={v} pid-only {t:16} says={short(r)!r} effect={r.get('effect')}",flush=True)
            p.terminate(); time.sleep(.4)
elif MODE=="bridge":
    # A GTK3 app that inherited NO_AT_BRIDGE=1 from an Electron host, then the same app with the bridge allowed.
    import re
    app=R+"/g3.py"; out=R+"/o.txt"; open(app,"w").write('''import gi,sys
gi.require_version("Gtk","3.0")
from gi.repository import Gtk
w=Gtk.Window(title="probe");e=Gtk.Entry();e.get_accessible().set_name("Probe");w.add(e);w.connect("destroy",Gtk.main_quit)
e.connect("changed",lambda x:open(sys.argv[1],"w").write(e.get_text()));w.show_all();Gtk.main()
''')
    for v in ("1","0"):
        p=sp.Popen([sys.executable,app,out],env=dict(os.environ,NO_AT_BRIDGE=v),stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(3)
        wins=call("list_windows",{"pid":p.pid}).get("windows") or []
        a={"pid":p.pid,"query":"Probe","include_screenshot":False}
        if wins: a["window_id"]=wins[0]["window_id"]
        s=call("get_window_state",a); m=re.search(r'\[(\d+)\][^\n]*"Probe"',s.get("tree_markdown") or "")
        typed=None
        if m:
            r=call("type_text",{"pid":p.pid,"window_id":s["window_id"],"element_token":f'{s["snapshot_id"]}:{m.group(1)}',"text":"ñ🙂ab"}); time.sleep(.4); typed=(open(out).read(),r.get("effect"))
        print(f"{LABEL} NO_AT_BRIDGE={v} windows={len(wins)} reason={str(s.get('degraded_reason') or s.get('_raw'))[:200]!r} row={bool(m)} typed={typed}",flush=True)
        p.terminate(); time.sleep(.4)
elif MODE=="layout":
    # Any layout: every marker found in a desktop screenshot, clicked as a screenshot pixel, must land on it, or the call refuses.
    # WINS_JSON: [[name,[r,g,b],mx,my,[x,y,w,h]],...] in layout coordinates.
    from PIL import Image
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    open(R+"/w.py","w").write("""import json,sys
from PyQt6 import QtWidgets,QtGui
name,rgb,mx,my,L=sys.argv[1:6]; mx,my=int(mx),int(my); log=open(L,"a",buffering=1)
class C(QtWidgets.QWidget):
    def paintEvent(self,_):
        p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor("#202020")); p.fillRect(mx,my,60,60,QtGui.QColor(*map(int,rgb.split(","))))
    def mousePressEvent(self,e):
        log.write(json.dumps([name,e.position().x(),e.position().y()])+"\\n")
    def mouseReleaseEvent(self,e):
        log.write(json.dumps([name+":release",e.position().x(),e.position().y()])+"\\n")
    def wheelEvent(self,e):
        log.write(json.dumps([name+":wheel",e.position().x(),e.position().y()])+"\\n")
a=QtWidgets.QApplication(sys.argv); w=C(); w.setWindowTitle(name); w.resize(500,400); w.show(); a.exec()
""")
    L=R+"/m.log"; open(L,"w")
    WINS=json.loads(os.environ["WINS_JSON"]); procs={}
    for n,c,mx,my,fr in WINS:
        procs[n]=sp.Popen([sys.executable,R+"/w.py",n,",".join(map(str,c)),str(mx),str(my),L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(1.2); print(LABEL,n,"frame",kw("frame",n,*fr).get("frame"),flush=True)
    time.sleep(.8)
    z=call("get_screen_size",{}); print(LABEL,"get_screen_size:",json.dumps({k:z.get(k) for k in ("width","height","scale_factor","monitors","_raw") if k in z})[:400],flush=True)
    p=R+"/d.png"; s=call("get_desktop_state",{"screenshot_out_file":p}); print(LABEL,"get_desktop_state:",json.dumps({k:s.get(k) for k in ("screen_width","screen_height","screenshot_width","screenshot_height","scale_factor","_raw") if k in s})[:300],flush=True)
    print(LABEL,"listed:",[(w.get("title"),w.get("bounds"),w.get("x"),w.get("y")) for w in (s.get("windows") or [])][:6],flush=True)
    if os.path.exists(p):
        im=Image.open(p).convert("RGB"); print(LABEL,"image",im.size,flush=True)
        if os.environ.get("KEEP"): im.save(os.environ["KEEP"]+"/"+LABEL+".png")
        def bbox(c):
            b=im.tobytes(); W=im.size[0]; t=bytes(c); xs=[];ys=[]
            for i in range(0,len(b),3):
                if b[i:i+3]==t: xs.append((i//3)%W); ys.append((i//3)//W)
            return (min(xs),max(xs),min(ys),max(ys)) if xs else None
        hits=0
        for n,c,mx,my,fr in WINS:
            bb=bbox(c)
            if not bb: print(LABEL,"MISSING",n,"marker not in screenshot",flush=True); continue
            x,y=(bb[0]+bb[1])//2,(bb[2]+bb[3])//2; n0=sum(1 for _ in open(L)); r=call("click",{"target":{"kind":"desktop","display_id":"primary"},"x":x,"y":y}); time.sleep(.7)
            rows=[r for r in (json.loads(l) for l in open(L)) ][n0:]; rows=[r for r in rows if ":" not in r[0]]; ev=rows[-1] if rows else None
            hit=bool(ev and ev[0]==n and mx-2<=ev[1]<mx+62 and my-2<=ev[2]<my+62); hits+=hit
            print(f"{LABEL} {n}: marker px {bb} clicked {(x,y)} window got {ev} => {'ON TARGET' if hit else 'MISSED'} effect={r.get('effect')} {str(r.get('_raw') or '')[:150]}",flush=True)
        print(f"{LABEL} RESULT {hits}/{len(WINS)}",flush=True)
        if os.environ.get("TOOLS"):
            # Every other desktop tool, at the first marker's screenshot point. The real pointer and the window's log are the truth.
            n,c,mx,my,fr=WINS[0]; bb=bbox(c); x,y=(bb[0]+bb[1])//2,(bb[2]+bb[3])//2; desk={"kind":"desktop","display_id":"primary"}
            r=call("move_cursor",{"target":desk,"x":x+3,"y":y+3}); time.sleep(.4); print(f"{LABEL} TOOL move_cursor to frame {(x+3,y+3)}: real pointer {kw('cursor')} {str(r.get('_raw') or r.get('effect'))[:120]}",flush=True)
            cp=call("get_cursor_position",{}); print(f"{LABEL} TOOL get_cursor_position: {(cp.get('x'),cp.get('y'))} want {(x+3,y+3)}",flush=True)
            n0=sum(1 for _ in open(L)); r=call("scroll",{"target":desk,"x":x,"y":y,"direction":"down","amount":1}); time.sleep(.6); rows=[json.loads(l) for l in open(L)][n0:]; print(f"{LABEL} TOOL scroll at {(x,y)}: real pointer {kw('cursor')} window log {rows[:2]} {str(r.get('_raw') or r.get('effect'))[:120]}",flush=True)
            n0=sum(1 for _ in open(L)); r=call("drag",{"target":desk,"from_x":x,"from_y":y,"to_x":x+40,"to_y":y+20,"steps":5,"duration_ms":200}); time.sleep(.6); rows=[json.loads(l) for l in open(L)][n0:]; print(f"{LABEL} TOOL drag {(x,y)}->{(x+40,y+20)}: window log {rows[:3]} {str(r.get('_raw') or r.get('effect'))[:120]}",flush=True)
        for pt in json.loads(os.environ.get("PROBES","[]")):
            n0=sum(1 for _ in open(L)); r=call("click",{"target":{"kind":"desktop","display_id":"primary"},"x":pt[0],"y":pt[1]}); time.sleep(.6); rows=[json.loads(l) for l in open(L)][n0:]
            print(f"{LABEL} probe click {tuple(pt)}: real pointer {kw('cursor')} got {rows} {str(r.get('_raw') or r.get('code') or r.get('effect'))[:170]}",flush=True)
    for p in procs.values(): p.terminate()
elif MODE in("monitors","x11"):
    from PIL import Image
    import re
    ok=[]
    def check(n,v,d=""):
        ok.append(bool(v)); print(f"{LABEL:8}{'PASS' if v else 'FAIL'} {n} | {str(d)[:135]}",flush=True)
    kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
    desk={"kind":"desktop","display_id":"primary"}
    def shot():
        p=R+"/d.png"
        if os.path.exists(p): os.remove(p)
        s=call("get_desktop_state",{"screenshot_out_file":p})
        return (Image.open(p).convert("RGB") if os.path.exists(p) else None),s
    def bbox(im,rgb):
        b=im.tobytes(); W=im.size[0]; t=bytes(rgb); xs=[];ys=[]
        for i in range(0,len(b),3):
            if b[i:i+3]==t: xs.append((i//3)%W); ys.append((i//3)//W)
        return (min(xs),max(xs),min(ys),max(ys)) if xs else None
    def last(L):
        rows=[json.loads(l) for l in open(L)]
        return rows[-1] if rows else None
if MODE=="monitors":
    # Screenshot pixels, clicks and window captures across outputs. Ground truth is the press each window logged.
    open(R+"/w.py","w").write("""import json,sys
from PyQt6 import QtWidgets,QtGui
name,rgb,mx,my,L=sys.argv[1:6]; mx,my=int(mx),int(my); log=open(L,"a",buffering=1)
class C(QtWidgets.QWidget):
    def paintEvent(self,_):
        p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor("#202020")); p.fillRect(mx,my,60,60,QtGui.QColor(*map(int,rgb.split(","))))
    def mousePressEvent(self,e):
        log.write(json.dumps([name,e.position().x(),e.position().y()])+"\\n")
a=QtWidgets.QApplication(sys.argv); w=C(); w.setWindowTitle(name); w.resize(500,400); w.show(); a.exec()
""")
    L=R+"/m.log"; open(L,"w")
    WINS=[("MonLeft",(255,0,255),100,100,(50,100,500,400)),("MonLeftLow",(255,255,0),100,100,(200,1100,500,400)),("MonRight",(0,255,255),100,100,(1000,100,500,400)),("MonRightEdge",(0,255,0),380,300,(2400,700,500,400)),("MonSpan",(255,128,0),300,100,(650,500,500,400))]
    procs={}
    for n,c,mx,my,fr in WINS:
        procs[n]=sp.Popen([sys.executable,R+"/w.py",n,",".join(map(str,c)),str(mx),str(my),L],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(1.2); kw("frame",n,*fr)
    time.sleep(.8)
    z=call("get_screen_size",{}); check("screen is the logical bounding box",(z.get("width"),z.get("height"))==(2912,1536),z)
    im,s=shot(); check("desktop screenshot is the logical bounding box",im and im.size==(2912,1536),(im.size if im else None,str(s.get("_raw") or "")[:90]))
    if im:
        im.save(R+"/layout.png")
        for n,c,mx,my,fr in WINS:
            bb=bbox(im,c); check(f"{n}: marker found in the screenshot",bool(bb),bb)
            if bb:
                x,y=(bb[0]+bb[1])//2,(bb[2]+bb[3])//2; r=call("click",{"target":desk,"x":x,"y":y}); time.sleep(.7); ev=last(L)
                hit=ev and ev[0]==n and mx-2<=ev[1]<mx+62 and my-2<=ev[2]<my+62
                check(f"{n}: click at screenshot point {(x,y)} lands on its marker",hit,(ev,str(r.get('_raw') or r.get('effect'))[:60]))
        n0=sum(1 for _ in open(L)); r=call("click",{"target":desk,"x":2500,"y":1400}); time.sleep(.6); n1=sum(1 for _ in open(L))
        check("a point in the frame on no output hits no window",n1==n0,(n1-n0,str(r.get('_raw') or r.get('code') or r.get('effect'))[:100]))
    for n,c,mx,my,fr in WINS:
        p=procs[n]; w=(call("list_windows",{"pid":p.pid}).get("windows") or [None])[0]
        if not w: check(f"{n}: listed",False); continue
        b=w["bounds"]; g=kw("find",n); check(f"{n}: bounds match KWin",[b["x"],b["y"],b["width"],b["height"]]==[round(v) for v in g["frame"]],(b,g["frame"],g.get("output")))
        png=R+"/w.png"
        if os.path.exists(png): os.remove(png)
        s=call("get_window_state",{"pid":p.pid,"window_id":w["window_id"],"include_accessibility_tree":False,"screenshot_out_file":png})
        if not os.path.exists(png): check(f"{n}: window capture",False,str(s.get("_raw") or s.get("degraded_reason"))[:110]); continue
        wi=Image.open(png).convert("RGB"); bw=bbox(wi,c); bd=bbox(im,c) if im else None
        # Where the desktop screenshot shows the marker, relative to the window's frame, is where the capture must show it.
        want=(bd[0]-g["frame"][0],bd[2]-g["frame"][1]) if bd else None
        check(f"{n}: capture is its logical size with its marker in place",wi.size==(500,400) and bw and want and abs(bw[0]-want[0])<=2 and abs(bw[2]-want[1])<=2,(wi.size,bw,want))
    f=call("bring_to_front",{"pid":procs["MonLeftLow"].pid,"window_id":(call("list_windows",{"pid":procs["MonLeftLow"].pid}).get("windows") or [{}])[0].get("window_id")}); time.sleep(.3); check("bring_to_front on the portrait output",kw("find","MonLeftLow")["active"],str(f.get("_raw") or "ok")[:90])
    print(f"{LABEL} RESULT {sum(ok)}/{len(ok)}",flush=True)
    for p in procs.values(): p.terminate()
elif MODE=="x11":
    # Xwayland apps next to a driver that also sees DISPLAY, as on a normal Plasma session.
    QT="""import json,sys
from PyQt6 import QtWidgets,QtGui
out,L=sys.argv[1:3]; log=open(L,"a",buffering=1)
class C(QtWidgets.QWidget):
    def paintEvent(self,_):
        p=QtGui.QPainter(self); p.fillRect(self.rect(),QtGui.QColor("#202020")); p.fillRect(300,200,60,60,QtGui.QColor(255,0,255))
    def mousePressEvent(self,e): log.write(json.dumps([e.position().x(),e.position().y()])+"\\n")
a=QtWidgets.QApplication(sys.argv); w=C(); w.setWindowTitle("X11App"); w.resize(600,400)
e=QtWidgets.QLineEdit(w); e.setAccessibleName("Probe"); e.setGeometry(10,10,400,34); e.textChanged.connect(lambda t:open(out,"w").write(t)); w.show(); e.setFocus(); a.exec()
"""
    GTK="""import gi,json,sys
gi.require_version("Gtk","3.0"); gi.require_version("Gdk","3.0")
from gi.repository import Gtk,Gdk
out,L=sys.argv[1:3]; log=open(L,"a",buffering=1)
w=Gtk.Window(title="X11App"); w.set_default_size(600,400); o=Gtk.Overlay(); d=Gtk.EventBox(); f=Gtk.Fixed(); m=Gtk.Box(); m.set_name("marker"); m.set_size_request(60,60); f.put(m,300,200); d.add(f); o.add(d)
css=Gtk.CssProvider(); css.load_from_data(b"eventbox{background:#202020} #marker{background:#ff00ff}")
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
d.connect("button-press-event",lambda _,e:log.write(json.dumps([e.x,e.y])+"\\n"))
e=Gtk.Entry(); e.set_halign(Gtk.Align.START); e.set_valign(Gtk.Align.START); e.set_size_request(400,34); e.get_accessible().set_name("Probe"); o.add_overlay(e)
e.connect("changed",lambda x:open(out,"w").write(e.get_text())); w.add(o); w.connect("destroy",Gtk.main_quit); w.show_all(); e.grab_focus(); Gtk.main()
"""
    print(LABEL,"DISPLAY",os.environ.get("DISPLAY"),"XAUTHORITY",bool(os.environ.get("XAUTHORITY")),flush=True)
    for tk,code,env in (("Qt",QT,{"QT_QPA_PLATFORM":"xcb"}),("GTK3",GTK,{"GDK_BACKEND":"x11"})):
        app=R+"/x.py"; out=R+"/x.txt"; L=R+"/x.log"; open(app,"w").write(code); open(out,"w").close(); open(L,"w").close()
        p=sp.Popen([sys.executable,app,out,L],env=dict(os.environ,**env),stdout=sp.DEVNULL,stderr=open(R+"/x.err","w")); time.sleep(3)
        g=kw("find","X11App")
        if not g: check(f"{tk}: the window opened on X11",False,open(R+"/x.err").read()[-150:]); p.terminate(); continue
        check(f"{tk}: it is an X11 client, on a socket of Xwayland",any("/tmp/.X11-unix/X0" in l for l in open(f"/proc/{p.pid}/net/unix")),(g.get("cls")))
        kw("frame","X11App",300,150,600,400); time.sleep(.5); g=kw("find","X11App")
        ws=call("list_windows",{"pid":p.pid}).get("windows") or []
        check(f"{tk}: listed",bool(ws),ws[:1])
        if ws:
            w=ws[0]; b=w["bounds"]; fr=[round(v) for v in g["frame"]]; check(f"{tk}: bounds match KWin",all(abs(a-c)<=1 for a,c in zip([b["x"],b["y"],b["width"],b["height"]],fr)),(b,fr))
            png=R+"/w.png"
            if os.path.exists(png): os.remove(png)
            s=call("get_window_state",{"pid":p.pid,"window_id":w["window_id"],"include_accessibility_tree":False,"screenshot_out_file":png})
            if os.path.exists(png):
                wi=Image.open(png).convert("RGB"); bb=bbox(wi,(255,0,255)); dim,_=shot(); bd=bbox(dim,(255,0,255)) if dim else None
                # Xwayland may scale the app, so the marker's place comes from the desktop screenshot, relative to the frame.
                want=(bd[0]-g["frame"][0],bd[2]-g["frame"][1]) if bd else None
                top=sorted(wi.getcolors(1<<24),reverse=True)[:4]
                if os.environ.get("KEEP"): wi.save(os.environ["KEEP"]+f"/{tk}-win.png"); dim and dim.save(os.environ["KEEP"]+f"/{tk}-desk.png")
                check(f"{tk}: window capture has its marker where the desktop shows it",bb and want and abs(wi.size[0]-fr[2])<=1 and abs(bb[0]-want[0])<=3 and abs(bb[2]-want[1])<=3,(wi.size,bb,want,top if not bb else ""))
            else: check(f"{tk}: window capture",False,str(s.get("_raw") or s.get("degraded_reason"))[:110])
            s=call("get_window_state",{"pid":p.pid,"window_id":w["window_id"],"query":"Probe","include_screenshot":False}); m=re.search(r'\[(\d+)\][^\n]*"Probe"',s.get("tree_markdown") or "")
            check(f"{tk}: accessibility tree has the field",bool(m),str(s.get("degraded_reason") or s.get("_raw") or "")[:110])
            if m:
                r=call("type_text",{"pid":p.pid,"window_id":w["window_id"],"element_token":f'{s["snapshot_id"]}:{m.group(1)}',"text":"ñ🙂ab"}); time.sleep(.5); got=open(out).read(); check(f"{tk}: typing by element is exact",got=="ñ🙂ab",(got,r.get("effect"),str(r.get("_raw") or "")[:60]))
            f=call("bring_to_front",{"pid":p.pid,"window_id":w["window_id"]}); time.sleep(.4); check(f"{tk}: bring_to_front",kw("find","X11App")["active"],str(f.get("_raw") or "ok")[:90])
        im,s=shot(); bb=bbox(im,(255,0,255)) if im else None; check(f"{tk}: marker in the desktop screenshot",bool(bb),(bb,str(s.get("_raw") or "")[:80]))
        if bb:
            x,y=(bb[0]+bb[1])//2,(bb[2]+bb[3])//2; r=call("click",{"target":desk,"x":x,"y":y}); time.sleep(.7); ev=last(L); check(f"{tk}: desktop click lands on the marker",ev and 296<=ev[0]<=364 and 196<=ev[1]<=264,(ev,(x,y),str(r.get("_raw") or r.get("effect"))[:50]))
        before=open(out).read(); kw("activate","X11App"); time.sleep(.3)
        print(LABEL,tk,"active before desktop typing:",kw("find","X11App")["active"],flush=True)
        r=call("type_text",{"scope":"desktop","text":"ñandú €5"}); time.sleep(1.2); got=open(out).read()[len(before):]; check(f"{tk}: desktop typing reaches the focused field",got=="ñandú €5",(got,r.get("effect"),str(r.get("_raw") or "")[:70]))
        p.terminate(); time.sleep(.6)
    print(f"{LABEL} RESULT {sum(ok)}/{len(ok)}",flush=True)
stop.set(); D.terminate()
