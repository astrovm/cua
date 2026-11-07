#!/usr/bin/env python3
"""Type through the real driver on real KWin with several XKB layouts, Caps Lock, or long text.

Ground truth is the field's own contents. One line per case. Run through run.sh:
  run.sh layouts L cua-driver XKB_LAYOUTS=de,us [XWAYLAND=1]
  run.sh long L cua-driver [XWAYLAND=1]
Without XKB_LAYOUTS the session has plain us. XKB_VARIANT still applies.
"""
import json, os, subprocess as sp, sys, threading, time
import dbus
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
from dbus.mainloop.glib import DBusGMainLoop

BIN, SCENARIO = sys.argv[1:3]
R = os.environ["SCRATCH_DIR"]
SOCK = R + "/d.sock"
os.chdir(R)
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

def start_driver():
    d = sp.Popen([BIN, "serve", "--socket", SOCK, "--pid-file", R + "/d.pid"], stdout=open(R + "/d.log", "w"), stderr=sp.STDOUT,
                 env=dict(os.environ, REIS_DEBUG="1") if os.environ.get("REIS_LOG") else None)
    for _ in range(300):
        if os.path.exists(SOCK):
            break
        time.sleep(.1)
    time.sleep(.3)
    return d

def call(tool, args, timeout=170):
    args = dict(args)
    args.setdefault("session", "layouts")
    r = sp.run([BIN, "call", "--socket", SOCK, tool, json.dumps(args)], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()

QT = '''import sys
from PyQt6 import QtWidgets, QtCore
L = sys.argv[1]
a = QtWidgets.QApplication(sys.argv)
w = QtWidgets.QPlainTextEdit(); w.resize(600, 200); w.setWindowTitle("Target")
def save():
    open(L + ".tmp", "w").write(w.toPlainText()); import os; os.replace(L + ".tmp", L)
t = QtCore.QTimer(); t.timeout.connect(save); t.start(40)
w.show(); a.exec()
'''
open("qtapp.py", "w").write(QT)

def field(plat):
    L = f"{R}/qt-{plat}.txt"
    open(L, "w").close()
    p = sp.Popen([sys.executable, "qtapp.py", L], env=dict(os.environ, QT_QPA_PLATFORM=plat), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    time.sleep(3)
    return p, L

def read(L):
    return open(L, encoding="utf-8").read()

def group(index=None):
    base = ["gdbus", "call", "--session", "--dest", "org.kde.keyboard", "--object-path", "/Layouts", "--method"]
    if index is not None:
        for _ in range(40):
            sp.run(base + ["org.kde.KeyboardLayouts.setLayout", str(index)], capture_output=True, text=True, timeout=10)
            time.sleep(.25)
            if f"uint32 {index}" in sp.run(base + ["org.kde.KeyboardLayouts.getLayout"], capture_output=True, text=True, timeout=10).stdout:
                break
    out = sp.run(base + ["org.kde.KeyboardLayouts.getLayout"], capture_output=True, text=True, timeout=10).stdout.strip()
    return out

class Caps:
    """Press Caps Lock through the RemoteDesktop portal, as another input device would."""
    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        obj = self.bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
        self.rd = dbus.Interface(obj, "org.freedesktop.portal.RemoteDesktop")
        self.n = 0
        got = self.request(lambda o: self.rd.CreateSession(o), {"session_handle_token": "capssession"})
        self.session = str(got["session_handle"])
        self.request(lambda o: self.rd.SelectDevices(self.session, o), {"types": dbus.UInt32(1)})
        self.request(lambda o: self.rd.Start(self.session, "", o), {})

    def request(self, call_it, options):
        self.n += 1
        token = f"caps{self.n}{os.getpid()}"
        sender = self.bus.get_unique_name()[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        loop = GLib.MainLoop()
        result = {}
        def done(code, results):
            result.update(results)
            result["_code"] = int(code)
            loop.quit()
        match = self.bus.add_signal_receiver(done, "Response", "org.freedesktop.portal.Request", path=path)
        call_it(dict(options, handle_token=token))
        GLib.timeout_add_seconds(30, loop.quit)
        loop.run()
        match.remove()
        if result.get("_code") != 0:
            raise RuntimeError(f"portal said {result}")
        return result

    def press(self, code=58):
        self.rd.NotifyKeyboardKeycode(self.session, {}, code, dbus.UInt32(1))
        self.rd.NotifyKeyboardKeycode(self.session, {}, code, dbus.UInt32(0))
        time.sleep(.4)

def case(name, L, text, expected=None, wait=1.5):
    expected = text.replace("\r\n", "\n") if expected is None else expected
    before = read(L)
    t = time.time()
    out = call("type_text", {"scope": "desktop", "text": text})
    took = time.time() - t
    end = time.time() + wait
    while time.time() < end and read(L)[len(before):] != expected:
        time.sleep(.03)
    got = read(L)[len(before):]
    refused = "no key for" in out or "foreground_unavailable" in out
    verdict = "exact" if got == expected else ("refused" if refused and not got else "WRONG")
    err = "" if verdict == "exact" and not refused else f" err={out[:150]!r}"
    print(f"KEYS {name:34} sent={text!r:14} got={got!r:14} {verdict} {took:.2f}s{err}", flush=True)
    return verdict

def clients():
    return ["wayland", "xcb"] if os.environ.get("XWAYLAND") else ["wayland"]

def layouts():
    layouts = os.environ.get("XKB_LAYOUTS", "us").split(",")
    second = len(layouts) - 1
    print(f"KEYS layouts {layouts} session starts on {group()}", flush=True)
    # A layout other than the first is active before the driver ever talks to the compositor.
    group(second)
    print(f"KEYS active {layouts[second]} (index {group()})", flush=True)
    d = start_driver()
    for plat in clients():
        p, L = field(plat)
        tag = f"{plat} {layouts[second]} active"
        for t in ("y\nz", "yz", "y-z/", "ab\r\nZY"):
            case(tag, L, t)
        if second:
            group(0)
            tag = f"{plat} {layouts[0]} active, switched"
            for t in ("y\nz", "yz", "y-z/"):
                case(tag, L, t)
            group(second)
        p.terminate(); p.wait(5); time.sleep(.5)
    caps = Caps()
    caps.press()
    for plat in clients():
        p, L = field(plat)
        tag = f"{plat} Caps Lock on"
        for t in ("a", "A", "a\nB", "Hello 123", "ñ"):
            case(tag, L, t)
        p.terminate(); p.wait(5); time.sleep(.5)
    caps.press()
    d.terminate()

def long_text():
    d = start_driver()
    cases = {
        "200 lines + emoji": "\n".join(f"line {i}" for i in range(200)) + "🙂",
        "200 lines": "\n".join(f"line {i}" for i in range(200)),
        "200 long lines": "\n".join(f"line {i} " + "abcdefghij" * 6 for i in range(200)),
        "one line": "plain text",
    }
    only = os.environ.get("LONG_CASE")
    for plat in clients():
        for name, text in cases.items():
            if only and only != name:
                continue
            p, L = field(plat)
            t = time.time()
            out = call("type_text", {"scope": "desktop", "text": text}, timeout=160)
            took = time.time() - t
            at_return = len(read(L))
            time.sleep(1.5)
            soon = len(read(L))
            end = time.time() + 30
            while time.time() < end and len(read(L)) < len(text):
                time.sleep(.2)
            time.sleep(1.5)
            final = read(L)
            state = "exact" if final == text else ("empty" if not final else "duplicated" if len(final) > len(text) else "WRONG")
            print(f"KEYS {plat} {name:20} chars={len(text)} took={took:.2f}s at_return={at_return} after1.5s={soon} final={len(final)} {state} out={out[:170]!r}", flush=True)
            p.terminate(); p.wait(5); time.sleep(.5)
    d.terminate()

def modlog():
    """What the compositor tells the driver about modifiers and layout, step by step."""
    seen = [0]
    def show(tag):
        lines = [l.strip() for l in open(R + "/d.log", errors="replace") if ".modifiers(" in l]
        fresh = lines[seen[0]:]
        seen[0] = len(lines)
        print(f"KEYS {tag:30} active={group()} new={[l.split('.modifiers')[1] for l in fresh]}", flush=True)
    def press(tag, text):
        call("type_text", {"scope": "desktop", "text": text})
        time.sleep(.3)
        show(tag)
    layouts = os.environ.get("XKB_LAYOUTS", "us").split(",")
    group(1)
    d = start_driver()
    p, L = field("wayland")
    show("started, us active")
    press("typed a\\nb", "a\nb")
    press("typed A\\nB (Shift)", "A\nB")
    group(0); show("switched to de")
    press("typed a\\nb", "a\nb")
    press("typed A\\nB (Shift)", "A\nB")
    group(1); show("switched to us")
    press("typed A\\nB (Shift)", "A\nB")
    caps = Caps()
    caps.press(); show("Caps pressed")
    press("typed a\\nb under caps", "a\nb")
    caps.press(); show("Caps released")
    # A hotkey, then text right away.
    call("hotkey", {"scope": "desktop", "keys": ["ctrl", "a"]}); show("after ctrl+a")
    press("typed right after hotkey", "c\nd")
    print(f"KEYS field {read(L)!r}", flush=True)
    p.terminate(); d.terminate()

def texts():
    """Type each string of TEXTS (a JSON list), in each client."""
    d = start_driver()
    for plat in clients():
        p, L = field(plat)
        for t in json.loads(os.environ["TEXTS"]):
            case(f"{plat} {os.environ.get('XKB_LAYOUTS', 'us')} {os.environ.get('XKB_OPTIONS', '')}", L, t)
        p.terminate(); p.wait(5); time.sleep(.5)
    d.terminate()

def nodisplay():
    """Driver started without DISPLAY, while Xwayland runs."""
    os.environ.pop("DISPLAY", None)
    display = os.environ.pop("KEEP_DISPLAY", ":0")
    d = start_driver()
    for plat in clients():
        env = dict(os.environ, DISPLAY=display)
        L = f"{R}/qt-{plat}.txt"
        open(L, "w").close()
        p = sp.Popen([sys.executable, "qtapp.py", L], env=dict(env, QT_QPA_PLATFORM=plat), stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        time.sleep(3)
        for t in ("plain 1", "日本", "a\n日"):
            case(f"{plat} driver has no DISPLAY", L, t)
        p.terminate(); p.wait(5); time.sleep(.5)
    d.terminate()

def capsfirst():
    """Caps Lock already on, and the second layout active, when the driver starts."""
    group(1)
    caps = Caps()
    caps.press()
    d = start_driver()
    p, L = field("wayland")
    for t in ["a", "A", "a\nB", "Hello 123"]:
        case("Caps on before start", L, t)
    caps.press()
    p.terminate(); d.terminate()

def hungx():
    """Xwayland stopped: an X server that never answers."""
    d = start_driver()
    p, L = field("wayland")
    case("X answers", L, "plain 1")
    sp.run(["pkill", "-STOP", "Xwayland"])
    time.sleep(.5)
    tasks = lambda: len(os.listdir(f"/proc/{d.pid}/task"))
    fds = lambda: len(os.listdir(f"/proc/{d.pid}/fd"))
    before = (tasks(), fds())
    for i, t in enumerate(["plain 2", "plain 3", "\u65e5\u672c", "plain 4", "plain 5", "plain 6"]):
        case("X hung", L, t)
    print(f"KEYS threads,fds before {before} after {(tasks(), fds())}", flush=True)
    sp.run(["pkill", "-CONT", "Xwayland"])
    time.sleep(1)
    case("X back", L, "plain 7")
    p.terminate(); d.terminate()

def refusal():
    """The whole answer an agent gets when text is refused."""
    d = start_driver()
    p, L = field("wayland")
    for text in ["日\n本", "abc\u0008"]:
        out = call("type_text", {"scope": "desktop", "text": text})
        for line in out.splitlines():
            print("KEYS " + line[:230], flush=True)
    p.terminate(); d.terminate()

{"capsfirst": capsfirst, "hungx": hungx, "refusal": refusal, "layouts": layouts, "long": long_text, "modlog": modlog, "texts": texts, "nodisplay": nodisplay}[SCENARIO]()
stop.set()
if os.environ.get("REIS_LOG"):
    seen = [l.strip() for l in open(R + "/d.log", errors="replace") if "odifiers" in l or "keymap" in l.lower()]
    print(f"KEYS reis: {len(seen)} modifier/keymap lines", flush=True)
    for l in seen[:14]:
        print("KEYS reis " + l[:200], flush=True)
