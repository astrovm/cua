"""Direct AT-SPI access through the system typelib, for test setup and for timing it as a technique."""
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


def _app(pid):
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        a = desktop.get_child_at_index(i)
        if a and a.get_process_id() == pid:
            return a
    raise LookupError(f"no AT-SPI app for pid {pid}")


def _walk(n, name):
    if n.get_name() == name:
        return n
    for i in range(n.get_child_count()):
        c = n.get_child_at_index(i)
        if c:
            r = _walk(c, name)
            if r:
                return r
    return None


def find(pid, name):
    r = _walk(_app(pid), name)
    if r is None:
        raise LookupError(name)
    return r


def set_text(pid, name, text):
    return find(pid, name).get_editable_text_iface().set_text_contents(text)


def focus(pid, name):
    return find(pid, name).get_component_iface().grab_focus()


def text_of(pid, name):
    a = find(pid, name)
    return Atspi.Text.get_text(a, 0, Atspi.Text.get_character_count(a))
