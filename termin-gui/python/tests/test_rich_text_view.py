from tcgui.widgets.rich_text_view import RichTextView
from tcgui.widgets.events import KeyEvent
from tcbase import Key, Mods
import pytest


def test_set_html_preserves_lines_and_plain_text():
    view = RichTextView()

    view.set_html("<pre>A<br>B</pre>")

    assert view.text == "A\nB"


def test_set_html_reads_span_color_and_bold():
    view = RichTextView()

    view.set_html("<span style='color: #50fa7b; font-weight: bold;'>Writer</span>")

    segment = view.lines[0][0]
    assert segment.text == "Writer"
    assert segment.style.bold is True
    color = segment.style.color
    assert type(color).__name__ == "SrgbColor"
    assert color.r == pytest.approx(80 / 255.0)
    assert color.g == pytest.approx(250 / 255.0)
    assert color.b == pytest.approx(123 / 255.0)
    assert color.a == pytest.approx(1.0)


def test_set_text_replaces_rich_lines():
    view = RichTextView()
    view.set_html("<b>A</b>")

    view.text = "plain\ntext"

    assert view.text == "plain\ntext"
    assert view.lines[0][0].style.bold is False


class DummyUI:
    def __init__(self):
        self.clipboard = ""

    def set_clipboard_text(self, text):
        self.clipboard = text


def test_rich_text_view_select_all_and_copy_plain_text():
    view = RichTextView()
    view._ui = DummyUI()
    view.text = "plain\ntext"

    assert view.on_key_down(KeyEvent(Key.A, Mods.CTRL.value))
    assert view.selected_text() == "plain\ntext"
    assert view.on_key_down(KeyEvent(Key.C, Mods.CTRL.value))
    assert view._ui.clipboard == "plain\ntext"
