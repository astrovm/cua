#!/usr/bin/env python3
"""Minimal KWin scripting bridge: run JS inside KWin, get a JSON result back over D-Bus.

usage:
  kw.py list                     all normal windows
  kw.py find <title>             first window whose caption contains title
  kw.py activate <title>         focus it, print result
  kw.py frame <title> x y w h    set geometry
  kw.py cursor                   real pointer position (logical px)
  kw.py minimize <title> 0|1
  kw.py js '<body using emit(obj)>'
"""
import json, os, sys, tempfile, time
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

SVC = f"org.cubench.r{os.getpid()}"

PRE = """
function winfo(w){var f=w.frameGeometry, c=w.clientGeometry;return {id:String(w.internalId),title:w.caption,cls:w.resourceClass,pid:w.pid,
 active:w===workspace.activeWindow,min:w.minimized,xw:!!w.x11DesktopIds,normal:w.normalWindow,
 covered_by:covered(w),frame:[f.x,f.y,f.width,f.height],client:[c.x,c.y,c.width,c.height],output:w.output?w.output.name:null};}
function covered(w){var s=workspace.stackingOrder,seen=false,g=w.frameGeometry,o=[];for(var i=0;i<s.length;i++){var x=s[i];if(x===w){seen=true;continue;}if(!seen||x.minimized||x.hidden||!(x.onAllDesktops||x.desktops.indexOf(workspace.currentDesktop)>=0)||!(x.normalWindow||x.dialog||x.utility)||(x.resourceClass==="cua-driver"&&!x.wantsInput))continue;var f=x.frameGeometry;if(f.x<g.x+g.width&&g.x<f.x+f.width&&f.y<g.y+g.height&&g.y<f.y+f.height)o.push(x.caption);}return o;}
function emit(o){callDBus("%s","/","org.cubench.R","r",JSON.stringify(o));}
function find(t){var l=workspace.windowList();for(var i=0;i<l.length;i++){if(l[i].caption.indexOf(t)>=0)return l[i];}return null;}
""" % SVC


class R(dbus.service.Object):
    def __init__(self, bus, loop):
        super().__init__(bus, "/")
        self.loop, self.val = loop, None

    @dbus.service.method("org.cubench.R", in_signature="s")
    def r(self, s):
        self.val = s
        self.loop.quit()


def run(body, timeout=3000):
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName(SVC, bus)  # noqa: keep reference
    loop = GLib.MainLoop()
    r = R(bus, loop)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(PRE + body)
    scr = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting"), "org.kde.kwin.Scripting")
    plugin = f"cubench{os.getpid()}"
    sid = bus.call_blocking("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", "loadScript", "ss", (f.name, plugin))
    so = bus.get_object("org.kde.KWin", f"/Scripting/Script{sid}")
    GLib.timeout_add(timeout, loop.quit)
    dbus.Interface(so, "org.kde.kwin.Script").run()
    loop.run()
    try:
        dbus.Interface(so, "org.kde.kwin.Script").stop()
    except dbus.DBusException:
        pass
    scr.unloadScript(plugin)
    os.unlink(f.name)
    return json.loads(r.val) if r.val else None


def main():
    a = sys.argv[1:]
    cmd = a[0]
    q = lambda s: json.dumps(s)
    if cmd == "list":
        b = "var o=[];workspace.windowList().forEach(function(w){if(w.normalWindow)o.push(winfo(w));});emit(o);"
    elif cmd == "find":
        b = f"var w=find({q(a[1])});emit(w?winfo(w):null);"
    elif cmd == "activate":
        b = f"var w=find({q(a[1])});if(w){{w.minimized=false;workspace.activeWindow=w;emit(winfo(w));}}else emit(null);"
    elif cmd == "frame":
        x, y, wd, h = a[2:6]
        b = f"var w=find({q(a[1])});if(w){{w.frameGeometry={{x:{x},y:{y},width:{wd},height:{h}}};emit(winfo(w));}}else emit(null);"
    elif cmd == "cursor":
        b = "var c=workspace.cursorPos;emit([c.x,c.y]);"
    elif cmd == "minimize":
        b = f"var w=find({q(a[1])});if(w){{w.minimized={'true' if a[2]=='1' else 'false'};emit(winfo(w));}}else emit(null);"
    elif cmd == "active":
        b = "var w=workspace.activeWindow;emit(w?winfo(w):null);"
    elif cmd == "js":
        b = a[1]
    else:
        sys.exit(__doc__)
    print(json.dumps(run(b)))


if __name__ == "__main__":
    main()
