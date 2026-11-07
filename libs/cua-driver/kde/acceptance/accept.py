#!/usr/bin/env python3
"""Acceptance run on the real desktop. Ground truth is harness_qt.py and KWin, never the tool's reply."""
import json,os,struct,subprocess as sp,sys,time,zlib
import atspi_util as AU
N=os.environ["CUA_BIN"]; SOCK=os.environ["CUA_SOCK"]; S="accept"
kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
def call(t,a=None,to=40):
    a=dict(a or {}); a.setdefault("session",S)
    r=sp.run([N,"call","--socket",SOCK,t,json.dumps(a)],capture_output=True,text=True,timeout=to)
    try: return json.loads(r.stdout)
    except Exception: return {"_raw":(r.stdout+r.stderr)[:400]}
st=lambda:json.load(open("results/qt_state.json"))
EV="results/qt_events.jsonl"
def events(off): return [json.loads(l) for l in open(EV).read()[off:].splitlines()]
def png_size(p):
    with open(p,"rb") as f: d=f.read(24)
    return struct.unpack(">II",d[16:24])
res=[]
def check(name,ok,detail=""):
    res.append((name,bool(ok))); print(("PASS" if ok else "FAIL"),name,"|",str(detail)[:230],flush=True)
def short(r): return json.dumps({k:r.get(k) for k in ("isError","error","message","hint","code","effect") if k in r})[:220] or str(r)[:220]
def text(r):
    c=r.get("content") if isinstance(r,dict) else None
    return " ".join(x.get("text","") for x in c if isinstance(x,dict)) if c else json.dumps(r)
os.makedirs("results",exist_ok=True); open(EV,"a").close()
Q=sp.Popen(["python3","harness_qt.py"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.5)
t3=kw("active")
try:
    kw("frame","CU Bench Qt",1100,200,800,720); time.sleep(.3)
    r=call("get_screen_size"); print("screen",json.dumps(r)[:300])
    check("screen is the logical layout",'2912' in json.dumps(r) and '1536' in json.dumps(r),json.dumps(r)[:200])
    # 1. list_windows
    r=call("list_windows",{"pid":Q.pid}); w=(r.get("structuredContent") or r).get("windows") or []
    g=kw("find","CU Bench Qt"); print("kwin frame",g["frame"],"listed",json.dumps(w)[:300])
    wid=None
    if w:
        wid=w[0].get("window_id"); b=w[0].get("bounds") or w[0]
        check("list_windows bounds match KWin",[b.get("x"),b.get("y"),b.get("width"),b.get("height")]==g["frame"],(b,g["frame"]))
    else: check("list_windows finds the window",False,r)
    # 2. covered window capture. Put another window over it first.
    a=kw("activate","T3 Code") if False else None
    kw("js",'var w=find("CU Bench Qt");var l=workspace.windowList();for(var i=0;i<l.length;i++){if(l[i].caption.indexOf("T3 Code")>=0||l[i].normalWindow&&l[i]!==w&&l[i].output===w.output){workspace.activeWindow=l[i];break;}}emit(1);')
    time.sleep(.4); g=kw("find","CU Bench Qt"); print("covered_by",g["covered_by"],"active",g["active"])
    if wid:
        t=time.monotonic(); r=call("get_window_state",{"pid":Q.pid,"window_id":wid,"include_accessibility_tree":False,"screenshot_out_file":"results/new_covered.png"}); ms=(time.monotonic()-t)*1000
        have=os.path.exists("results/new_covered.png"); print("capture reply",text(r)[:260])
        check("window capture works without focus",have and "surface_identity_unproven" not in json.dumps(r),f"{ms:.0f}ms size={png_size('results/new_covered.png') if have else None} active={g['active']}")
        check("window screenshot is in the window frame",have and png_size('results/new_covered.png')==(g["frame"][2],g["frame"][3]),png_size('results/new_covered.png') if have else None)
        # 3. bring_to_front past focus stealing prevention
        r=call("bring_to_front",{"pid":Q.pid,"window_id":wid}); time.sleep(.4); g=kw("find","CU Bench Qt")
        check("bring_to_front activates",g["active"] and not g["covered_by"],text(r)[:160])
    if not kw("find","CU Bench Qt")["active"]: kw("activate","CU Bench Qt"); time.sleep(.3)
    g=kw("find","CU Bench Qt"); assert g["active"] and not g["covered_by"],"guard: window not in front"
    c=g["client"]; cv=st()["widgets"]["canvas"]
    # 4. screenshot frame equals input frame
    r=call("get_desktop_state",{"screenshot_out_file":"results/new_desktop.png"}); print("desktop keys",{k:(v if k!="elements" else "...") for k,v in (r.get("structuredContent") or {}).items() if k in("width","height","screenshot_width","screenshot_height","frame_scale","capture_id")})
    sz=png_size("results/new_desktop.png") if os.path.exists("results/new_desktop.png") else None
    check("desktop capture is in the logical frame",sz==(2912,1536),sz)
    lat=[]
    for i in range(10):
        t=time.monotonic(); r=call("get_desktop_state",{"screenshot_out_file":"results/new_desktop.png"},to=45); lat.append(round((time.monotonic()-t)*1000))
    print("desktop capture ms",lat); check("desktop capture never stalls",max(lat)<3000,lat)
    # 5. pixel read off that screenshot lands exactly
    lx,ly=300,150; X,Y=c[0]+cv[0]+lx,c[1]+cv[1]+ly; off=os.path.getsize(EV)
    call("click",{"target":{"kind":"desktop","display_id":"primary"},"x":X,"y":Y}); time.sleep(.3)
    p=[e for e in events(off) if e["ev"]=="canvas_press"]
    check("screenshot coordinate click is exact",p and abs(p[0]["x"]-lx)<=1 and abs(p[0]["y"]-ly)<=1,p[:1] or "no press")
    # 6. desktop typing, real layout
    assert kw("find","CU Bench Qt")["active"],"left window"
    for name,tx in [("ascii","Hello 123"),("symbols","!@#$[]{}|\\`~"),("spanish","ñandú ¿qué? €5"),("keypad and media key symbols","$(1+2)*3=€9")]:
        AU.set_text(Q.pid,"LineInput",""); AU.focus(Q.pid,"LineInput"); time.sleep(.15); assert kw("find","CU Bench Qt")["active"],"left window"
        call("type_text",{"scope":"desktop","text":tx}); time.sleep(.5); got=st()["line"]
        check(f"desktop typing {name}",got==tx,repr(got))
    AU.set_text(Q.pid,"MultiInput",""); AU.focus(Q.pid,"MultiInput"); time.sleep(.15); assert kw("find","CU Bench Qt")["active"],"left window"
    call("type_text",{"scope":"desktop","text":"uno\ndos\r\ntres"}); time.sleep(.5); got=st()["multi"]
    check("desktop typing line breaks",got=="uno\ndos\ntres",repr(got))
    # 7. refusal
    AU.set_text(Q.pid,"LineInput","before"); AU.focus(Q.pid,"LineInput"); time.sleep(.15); assert kw("find","CU Bench Qt")["active"],"left window"
    r=call("type_text",{"scope":"desktop","text":"ab🙂cd"}); time.sleep(.5); got=st()["line"]
    check("untypable text is refused whole",got=="before" and ("Nothing was typed" in json.dumps(r)),(got,text(r)[:170]))
    # 8. element typing after an emoji
    import re
    def token(query,label,**kw):
        st_=call("get_window_state",{"pid":Q.pid,"window_id":wid,"query":query,"include_screenshot":False,**kw})
        m=re.search(r'\[(\d+)\][^\n]*"'+re.escape(label)+'"',st_.get("tree_markdown") or "")
        return (f'{st_["snapshot_id"]}:{m.group(1)}' if m else None),st_
    for tx in ["Z🙂ab","ñ🙂 ok","日本語 🙂 end"]:
        AU.set_text(Q.pid,"MultiInput",""); tok,s_=token("MultiInput","MultiInput")
        r=call("type_text",{"pid":Q.pid,"window_id":wid,"element_token":tok,"text":tx}); time.sleep(.3); got=st()["multi"]
        check(f"element typing {tx!r}",got==tx,(repr(got),text(r)[:120]))
    # 9. combo list item: open it, then pick from the list
    tok,s_=token("alpha","alpha"); print("combo row",tok,(s_.get("tree_markdown") or "")[:300])
    r=call("click",{"pid":Q.pid,"window_id":wid,"element_token":tok}); time.sleep(.5); print("open reply",text(r)[:240])
    tok,s_=token("beta","beta"); print("beta row",tok,(s_.get("tree_markdown") or "")[:300])
    if tok:
        r=call("click",{"pid":Q.pid,"window_id":wid,"element_token":tok}); time.sleep(.5); print("pick reply",text(r)[:320])
        check("combo item click changes the value",st()["combo"]=="beta",repr(st()["combo"]))
    else: check("combo item is reachable",False,"no row")
    # 10. how image pixels relate to the frame
    r=call("get_window_state",{"pid":Q.pid,"window_id":wid,"screenshot_out_file":"results/new_win.png","query":"Btn4"})
    print({k:r.get(k) for k in ("window_bounds","screenshot_width","screenshot_height","frame_scale","screenshot_scale","coordinate_frame")}); print((r.get("tree_markdown") or "")[:260]); print(str(r.get("frame_note"))[:400]); print("png",png_size("results/new_win.png"))
    # 11. latency with a release-independent view
    lat=[]
    for _ in range(5):
        t=time.monotonic(); call("get_window_state",{"pid":Q.pid,"window_id":wid,"include_accessibility_tree":False,"screenshot_out_file":"results/new_win2.png"}); lat.append((time.monotonic()-t)*1000)
    print("capture ms",[round(x) for x in lat])
finally:
    Q.terminate()
    try: kw("activate",t3["title"])
    except Exception as e: print("restore failed",e)
print(f"{sum(o for _,o in res)}/{len(res)} passed"); print("failed:",[n for n,o in res if not o])
