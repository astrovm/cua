#!/usr/bin/env python3
"""Ground-truth Qt6 Wayland test window: logs every input event it really receives.

Writes JSON lines to results/qt_events.jsonl and keeps results/qt_state.json current.
The tools under test never see this file: it records what arrived, not what was sent.
"""
import json, os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
os.environ.setdefault("QT_LINUX_ACCESSIBILITY_ALWAYS_ON", "1")
from PyQt6 import QtCore, QtGui, QtWidgets

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.environ.get("CU_RESULTS", os.path.join(BASE, "results"))
LOG = open(os.path.join(RES, "qt_events.jsonl"), "a", buffering=1)
STATE = os.path.join(RES, "qt_state.json")
state = {"pid": os.getpid(), "active": False, "line": "", "multi": "", "clicks": {}, "toggles": {}, "combo": "",
         "slider": 0, "pos": None, "last_key": None}


def emit(kind, **kw):
    LOG.write(json.dumps({"t": time.monotonic(), "ev": kind, **kw}) + "\n")
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE)


class Canvas(QtWidgets.QWidget):
    """Custom-drawn surface with no accessible children: pixels are the only way in."""

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(600, 320)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.mark = None
        self.setAccessibleName("canvas")

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#20242c"))
        p.setPen(QtGui.QColor("#6b7688"))
        for x in range(0, self.width(), 100):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 100):
            p.drawLine(0, y, self.width(), y)
        if self.mark:
            p.setBrush(QtGui.QColor("#ff5050"))
            p.drawEllipse(QtCore.QPointF(*self.mark), 6, 6)

    def _m(self, kind, e):
        pos = e.position()
        state["pos"] = [pos.x(), pos.y()]
        emit(kind, x=pos.x(), y=pos.y(), btn=e.button().name, mods=e.modifiers().value)

    def mousePressEvent(self, e):
        self.mark = (e.position().x(), e.position().y())
        self.update()
        self._m("canvas_press", e)

    def mouseReleaseEvent(self, e):
        self._m("canvas_release", e)

    def mouseDoubleClickEvent(self, e):
        self._m("canvas_double", e)

    def mouseMoveEvent(self, e):
        pos = e.position()
        state["pos"] = [pos.x(), pos.y()]
        if e.buttons() != QtCore.Qt.MouseButton.NoButton:
            emit("canvas_drag", x=pos.x(), y=pos.y())
        else:
            emit("canvas_move", x=pos.x(), y=pos.y())

    def wheelEvent(self, e):
        emit("canvas_wheel", dy=e.angleDelta().y(), dx=e.angleDelta().x())


class Win(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CU Bench Qt")
        m = self.menuBar().addMenu("&Bench")
        act = m.addAction("&Menu Action")
        act.setShortcut("Ctrl+Shift+M")
        act.triggered.connect(lambda: self._click("menu"))
        c = QtWidgets.QWidget()
        self.setCentralWidget(c)
        v = QtWidgets.QVBoxLayout(c)
        g = QtWidgets.QGridLayout()
        for i in range(6):
            b = QtWidgets.QPushButton(f"Btn{i}")
            b.setAccessibleName(f"Btn{i}")
            b.setObjectName(f"Btn{i}")
            b.clicked.connect(lambda _=False, n=f"Btn{i}": self._click(n))
            g.addWidget(b, i // 3, i % 3)
        v.addLayout(g)
        h = QtWidgets.QHBoxLayout()
        self.chk = QtWidgets.QCheckBox("Check1")
        self.chk.setAccessibleName("Check1")
        self.chk.toggled.connect(lambda val: self._toggle("Check1", val))
        h.addWidget(self.chk)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(["alpha", "beta", "gamma"])
        self.combo.setAccessibleName("Combo1")
        self.combo.currentTextChanged.connect(self._combo)
        h.addWidget(self.combo)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName("Slider1")
        self.slider.valueChanged.connect(self._slider)
        h.addWidget(self.slider)
        v.addLayout(h)
        self.line = QtWidgets.QLineEdit()
        self.line.setAccessibleName("LineInput")
        self.line.textChanged.connect(self._line)
        v.addWidget(self.line)
        self.multi = QtWidgets.QPlainTextEdit()
        self.multi.setAccessibleName("MultiInput")
        self.multi.setMaximumHeight(90)
        self.multi.textChanged.connect(self._multi)
        v.addWidget(self.multi)
        self.canvas = Canvas()
        v.addWidget(self.canvas, 1)
        self.resize(800, 720)
        QtWidgets.QApplication.instance().installEventFilter(self)
        self.geom = QtCore.QTimer(self, interval=500, timeout=self._geom)
        self.geom.start()

    def _geom(self):
        data = {}
        for w in [self.line, self.multi, self.canvas] + self.findChildren(QtWidgets.QPushButton):
            tl = w.mapTo(self, QtCore.QPoint(0, 0))
            data[w.accessibleName()] = [tl.x(), tl.y(), w.width(), w.height()]
        state["widgets"] = data
        state["win_size"] = [self.width(), self.height()]
        tmp = STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE)

    def _click(self, n):
        state["clicks"][n] = state["clicks"].get(n, 0) + 1
        emit("clicked", name=n)

    def _toggle(self, n, v):
        state["toggles"][n] = v
        emit("toggled", name=n, value=v)

    def _combo(self, t):
        state["combo"] = t
        emit("combo", value=t)

    def _slider(self, v):
        state["slider"] = v
        emit("slider", value=v)

    def _line(self, t):
        state["line"] = t
        emit("line", value=t)

    def _multi(self):
        state["multi"] = self.multi.toPlainText()
        emit("multi", value=state["multi"])

    def eventFilter(self, o, e):
        t = e.type()
        if t == QtCore.QEvent.Type.WindowActivate and o is self:
            state["active"] = True
            emit("activate")
        elif t == QtCore.QEvent.Type.WindowDeactivate and o is self:
            state["active"] = False
            emit("deactivate")
        elif t == QtCore.QEvent.Type.KeyPress and isinstance(o, QtGui.QWindow):
            state["last_key"] = {"key": e.key(), "text": e.text(), "mods": e.modifiers().value}
            emit("key", key=e.key(), text=e.text(), mods=e.modifiers().value, auto=e.isAutoRepeat())
        return False


app = QtWidgets.QApplication(sys.argv)
app.setDesktopFileName("cu-bench-qt")
w = Win()
w.show()
emit("started", pid=os.getpid(), platform=app.platformName())
print(os.getpid(), app.platformName(), flush=True)
sys.exit(app.exec())
