from tcbase import Key, Mods

from tcgui.widgets.events import KeyEvent, TextEvent
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.text_input import TextInput


class DummyUI:
    def __init__(self):
        self.clipboard = ""

    def get_clipboard_text(self):
        return self.clipboard

    def set_clipboard_text(self, text):
        self.clipboard = text


def ctrl(key):
    return KeyEvent(key, Mods.CTRL.value)


def shift(key):
    return KeyEvent(key, Mods.SHIFT.value)


def test_text_input_copy_paste_and_replace_selection():
    ui = DummyUI()
    widget = TextInput()
    widget._ui = ui
    widget.text = "hello"
    widget.cursor_pos = len(widget.text)

    assert widget.on_key_down(ctrl(Key.A))
    assert widget.selected_text() == "hello"
    assert widget.on_key_down(ctrl(Key.C))
    assert ui.clipboard == "hello"

    assert widget.on_text_input(TextEvent("bye"))
    assert widget.text == "bye"
    assert widget.cursor_pos == 3
    assert not widget.has_selection

    widget.cursor_pos = 0
    ui.clipboard = "!"
    assert widget.on_key_down(ctrl(Key.V))
    assert widget.text == "!bye"
    assert widget.cursor_pos == 1


def test_text_input_shift_selection_and_cut():
    ui = DummyUI()
    widget = TextInput()
    widget._ui = ui
    widget.text = "abc"
    widget.cursor_pos = 3

    assert widget.on_key_down(shift(Key.LEFT))
    assert widget.selected_text() == "c"
    assert widget.on_key_down(shift(Key.LEFT))
    assert widget.selected_text() == "bc"

    assert widget.on_key_down(ctrl(Key.X))
    assert ui.clipboard == "bc"
    assert widget.text == "a"
    assert widget.cursor_pos == 1


def test_text_area_copy_paste_multiline_selection():
    ui = DummyUI()
    area = TextArea()
    area._ui = ui
    area.text = "one\ntwo\nthree"
    area.cursor_line = 0
    area.cursor_col = 1
    area.selection_anchor = (2, 2)

    assert area.selected_text() == "ne\ntwo\nth"
    assert area.on_key_down(ctrl(Key.C))
    assert ui.clipboard == "ne\ntwo\nth"

    ui.clipboard = "X\nY"
    assert area.on_key_down(ctrl(Key.V))
    assert area.text == "oX\nYree"
    assert (area.cursor_line, area.cursor_col) == (1, 1)
    assert not area.has_selection


def test_text_area_delete_selection_and_plain_text_input():
    area = TextArea()
    area.text = "alpha\nbeta"
    area.cursor_line = 0
    area.cursor_col = 2
    area.selection_anchor = (1, 2)

    assert area.on_text_input(TextEvent("Z"))
    assert area.text == "alZta"
    assert (area.cursor_line, area.cursor_col) == (0, 3)

