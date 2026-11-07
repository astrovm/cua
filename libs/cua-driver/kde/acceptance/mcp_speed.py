#!/usr/bin/env python3
"""Latency through one long-running `cua-driver mcp`, the route agents use. Ground truth is the harness window."""
import json,os,statistics as st,subprocess as sp,time
BIN=os.path.expanduser("~/.local/bin/cua-driver")
kw=lambda *a: json.loads(sp.check_output(["python3","kw.py",*map(str,a)],timeout=8))
M=sp.Popen([BIN,"mcp"],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.DEVNULL,text=True,bufsize=1,env=dict(os.environ,CUA_DRIVER_RS_ENABLE_WAYLAND="1"))
n=0
def rpc(m,p):
    global n; n+=1; M.stdin.write(json.dumps({"jsonrpc":"2.0","id":n,"method":m,"params":p})+"\n"); M.stdin.flush()
    while True:
        d=json.loads(M.stdout.readline())
        if d.get("id")==n: return d
def tool(name,a):
    t=time.perf_counter(); r=rpc("tools/call",{"name":name,"arguments":{**a,"session":"speed"}}); return (time.perf_counter()-t)*1000,r
def row(label,xs): print(f"{label:34} median {st.median(xs):7.1f} ms  min {min(xs):7.1f}  max {max(xs):7.1f}  n={len(xs)}",flush=True)
rpc("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"speed","version":"1"}})
M.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n"); M.stdin.flush()
Q=sp.Popen(["python3","harness_qt.py"],stdout=sp.DEVNULL,stderr=sp.DEVNULL); time.sleep(2.5)
S=lambda:json.load(open("results/qt_state.json"))
t3=kw("active")
try:
    import atspi_util as AU
    kw("frame","CU Bench Qt",1100,200,800,720); time.sleep(.3)
    _,r=tool("list_windows",{"pid":Q.pid}); wid=r["result"]["structuredContent"]["windows"][0]["window_id"]
    row("list_windows",[tool("list_windows",{"pid":Q.pid})[0] for _ in range(8)])
    row("window screenshot (to file)",[tool("get_window_state",{"pid":Q.pid,"window_id":wid,"include_accessibility_tree":False,"screenshot_out_file":"/tmp/cu-s.png"})[0] for _ in range(8)])
    row("element tree query",[tool("get_window_state",{"pid":Q.pid,"window_id":wid,"query":"Btn4","include_screenshot":False})[0] for _ in range(8)])
    row("desktop screenshot (to file)",[tool("get_desktop_state",{"screenshot_out_file":"/tmp/cu-d.png"})[0] for _ in range(8)])
    tool("bring_to_front",{"pid":Q.pid,"window_id":wid}); time.sleep(.3)
    g=kw("find","CU Bench Qt"); assert g["active"] and not g["covered_by"],"guard"
    c=g["client"]; cv=S()["widgets"]["canvas"]; X,Y=c[0]+cv[0]+300,c[1]+cv[1]+150
    row("desktop click",[tool("click",{"target":{"kind":"desktop","display_id":"primary"},"x":X,"y":Y})[0] for _ in range(10)])
    row("bring_to_front",[tool("bring_to_front",{"pid":Q.pid,"window_id":wid})[0] for _ in range(6)])
    AU.set_text(Q.pid,"LineInput",""); AU.focus(Q.pid,"LineInput"); time.sleep(.15); assert kw("find","CU Bench Qt")["active"]
    T="the quick brown fox jumps over the lazy dog ñandú 1234567890 "*2
    ms,_=tool("type_text",{"scope":"desktop","text":T})
    # The call returns before a busy app has handled every key. Wait until the text settles.
    last,t0=None,time.time()
    while time.time()-t0<6:
        cur=S()["line"]
        if cur==last and time.time()-t0>.6: break
        last=cur; time.sleep(.25)
    print(f"desktop typing {len(T)} chars: {ms:.0f} ms = {len(T)/(ms/1000):.0f} chars/s, exact={S()['line']==T}")
    _,r=tool("get_window_state",{"pid":Q.pid,"window_id":wid,"query":"LineInput","include_screenshot":False})
    print("load",os.getloadavg()[0])
finally:
    Q.terminate(); M.terminate()
    try: kw("activate",t3["title"])
    except Exception as e: print("restore failed",e)
