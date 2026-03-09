"""InputDialog — modal dialog to get a single text value from the user."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput


def show_input_dialog(
    ui,
    title: str,
    message: str,
    default: str = "",
    on_result: Callable[[str | None], None] | None = None,
) -> None:
    """Show a modal dialog asking the user for a text value.

    ``on_result`` is called with the entered string on OK, or ``None`` on Cancel.
    """
    content = VStack()
    content.spacing = 8

    if message:
        lbl = Label()
        lbl.text = message
        content.add_child(lbl)

    inp = TextInput()
    inp.text = default
    content.add_child(inp)

    dlg = Dialog()
    dlg.title = title
    dlg.content = content
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"

    def _on_result(btn: str) -> None:
        if on_result is not None:
            if btn == "OK":
                on_result(inp.text)
            else:
                on_result(None)

    dlg.on_result = _on_result
    dlg.show(ui)
