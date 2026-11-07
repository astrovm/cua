#!/usr/bin/env python3
"""Type every character through the real driver into Qt and Chrome, native Wayland and Xwayland.

Prints one line per client: how many arrived exactly, and for each that did not,
what the app saw. Chrome runs only if /chrome holds a Chrome install.
Run through run.sh: acceptance/container/run.sh keys branch path/to/cua-driver
"""
import difflib, http.server, json, os, shutil, subprocess as sp, sys, threading, time
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

BIN = sys.argv[1]
R = os.environ["SCRATCH_DIR"]
SOCK = R + "/d.sock"
CHARS = list("$()+*€¿ñéÑ<>/=-_!@#%^&[]{}|\\:;\"',.?~`aZ5 ")
os.chdir(R)
D = sp.Popen([BIN, "serve", "--socket", SOCK, "--pid-file", R + "/d.pid"], stdout=open(R + "/d.log", "w"), stderr=sp.STDOUT)
for _ in range(300):
    if os.path.exists(SOCK):
        break
    time.sleep(.1)
time.sleep(.3)

def call(tool, args):
    args = dict(args)
    args.setdefault("session", "keys")
    r = sp.run([BIN, "call", "--socket", SOCK, tool, json.dumps(args)], capture_output=True, text=True, timeout=60)
    return (r.stdout + r.stderr).strip()

stop = threading.Event()
def approve():
    def walk(n, o):
        o.append(n)
        for i in range(min(n.get_child_count(), 40)):
            c = n.get_child_at_index(i)
            if c:
                walk(c, o)
        return o
    while not stop.is_set():
        time.sleep(.4)
        try:
            d = Atspi.get_desktop(0)
            for i in range(d.get_child_count()):
                a = d.get_child_at_index(i)
                if a and "portal" in (a.get_name() or "").lower():
                    for n in walk(a, []):
                        if n.get_role_name() in ("button", "push button") and n.get_name() in ("Approve", "Allow", "Share", "Save", "OK"):
                            n.get_action_iface().do_action(0)
                            time.sleep(1)
        except Exception:
            pass
threading.Thread(target=approve, daemon=True).start()

class Client:
    text = ""
    events = []
    seq = 0
    ready = False

lock = threading.Lock()

client = Client()

def run_chars(name, proc):
    want, spans, refused_cases, n = "", [], [], 0
    cases = CHARS + ["a\nb", "c\r\nd", "日", "日\n本"]
    for ch in cases:
        expected = ch.replace("\r\n", "\n")
        before = client.text
        out = call("type_text", {"scope": "desktop", "text": ch})
        if "no key for" in out:
            # Without ei_text the layout has no key for these, and a clean refusal is right.
            if "日" in ch:
                n += 1
            else:
                refused_cases.append(ch)
            continue
        spans.append((len(want), len(want) + len(expected), ch))
        want += expected
        end = time.time() + 2
        while time.time() < end and client.text[len(before):] != expected:
            time.sleep(.02)
    # A slow app can show a character after its wait ended, so only the final text decides.
    end = time.time() + 8
    while time.time() < end and client.text != want:
        time.sleep(.05)
    # Line the final text up with what was sent. A case counts when all of it arrived.
    arrived = set()
    for block in difflib.SequenceMatcher(None, want, client.text, autojunk=False).get_matching_blocks():
        arrived.update(range(block.a, block.a + block.size))
    lost = [ch for start, stop, ch in spans if not all(i in arrived for i in range(start, stop))]
    if client.text != want and not lost:
        lost = ["(order or extra text)"]
    n += len(spans) - len(lost)
    note = " ".join([f"lost {lost!r}"] * bool(lost) + [f"refused {refused_cases!r}"] * bool(refused_cases))
    print(f"KEYS {name:16} {n}/{len(cases)} {note}" + ("" if client.text == want else f" FINAL {client.text!r}"), flush=True)
    proc.terminate()
    try:
        proc.wait(5)
    except sp.TimeoutExpired:
        proc.kill()
    time.sleep(1)

QT = '''import sys
from PyQt6 import QtWidgets
L = sys.argv[1]
ev = open(L + ".ev", "a", buffering=1)
class E(QtWidgets.QPlainTextEdit):
    def keyPressEvent(s, e):
        ev.write("%d/%s\\n" % (e.nativeScanCode(), e.text() or hex(e.key())))
        super().keyPressEvent(e)
a = QtWidgets.QApplication(sys.argv)
w = E(); w.resize(600, 200)
w.textChanged.connect(lambda: open(L, "w").write(w.toPlainText()))
w.show(); a.exec()
'''
open("qtapp.py", "w").write(QT)

def qt(plat):
    client.text, client.events = "", []
    L = f"{R}/qt-{plat}.txt"
    open(L, "w").close()
    open(L + ".ev", "w").close()
    p = sp.Popen([sys.executable, "qtapp.py", L], env=dict(os.environ, QT_QPA_PLATFORM=plat), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(3)
    live = threading.Event()
    def follow():
        while not live.is_set():
            client.text = open(L).read()
            client.events = [l.strip() for l in open(L + ".ev")]
            time.sleep(.05)
    threading.Thread(target=follow, daemon=True).start()
    run_chars("Qt " + plat, p)
    live.set()

PAGE = b"""<!doctype html><title>keys</title><textarea id=t autofocus rows=8 cols=60></textarea><script>
const t=document.getElementById('t');let seq=0;const send=(k,v)=>fetch('/'+k+'?'+(++seq),{method:'POST',body:v});
t.addEventListener('keydown',e=>send('ev',e.code+'/'+e.key));
t.addEventListener('input',()=>send('text',t.value));setInterval(()=>{t.focus();if(document.hasFocus()&&document.activeElement===t)send('ready','1')},300);</script>"""

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        s.send_response(200); s.send_header("content-type", "text/html"); s.end_headers(); s.wfile.write(PAGE)
    def do_POST(s):
        body = s.rfile.read(int(s.headers["content-length"])).decode()
        path, seq = s.path.split("?")
        if path == "/ready":
            client.ready = True
        elif path == "/text":
            with lock:
                if int(seq) > client.seq:
                    client.seq, client.text = int(seq), body
        else:
            client.events = client.events + [body]
        s.send_response(204); s.end_headers()
    def log_message(s, *a):
        pass

def chrome(plat):
    client.text, client.events, client.seq, client.ready = "", [], 0, False
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = f"{R}/chrome-{plat}"
    p = sp.Popen(["/chrome/chrome", "--no-sandbox", f"--ozone-platform={plat}", f"--user-data-dir={prof}", "--no-first-run", "--disable-gpu", "--password-store=basic",
                  "--disable-dev-shm-usage", f"--app=http://127.0.0.1:{srv.server_port}/"], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    # Chrome starts slowly under load, so wait until the page says its field has focus.
    end = time.time() + 40
    while time.time() < end and not client.ready:
        time.sleep(.1)
    time.sleep(.5)
    if not client.ready:
        print(f"KEYS Chrome {plat} never got focus", flush=True)
    run_chars("Chrome " + plat, p)
    srv.shutdown()

if "chrome-only" not in sys.argv:
    qt("wayland")
    qt("xcb")
if os.path.exists("/chrome/chrome"):
    chrome("wayland")
    chrome("x11")
stop.set()
D.terminate()
