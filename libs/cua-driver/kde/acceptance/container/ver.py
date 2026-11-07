import subprocess as sp,sys,time
L=sys.argv[1]; time.sleep(1.5)
r=sp.run(["gdbus","introspect","--session","--dest","org.kde.KWin","--object-path","/KWin"],capture_output=True,text=True,timeout=15)
print(L,"introspect rc",r.returncode,(r.stderr)[:160],flush=True)
for line in r.stdout.splitlines():
    if any(k in line.lower() for k in("support","version")): print(L," ",line.strip()[:120],flush=True)
r=sp.run(["gdbus","call","--session","--dest","org.kde.KWin","--object-path","/KWin","--method","org.kde.KWin.supportInformation"],capture_output=True,text=True,timeout=15)
out=r.stdout+r.stderr; print(L,"rc",r.returncode,"len",len(out),out[:170].replace("\\n"," | "),flush=True)
print(L,"lines",[l for l in out.split("\\n") if "ersion" in l][:4],flush=True)
