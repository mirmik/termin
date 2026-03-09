"""MessageBox — convenience modal alert / confirmation dialogs."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.theme import current_theme as _t


class Buttons:
    """Common button set presets."""
    OK = ["OK"]
    OK_CANCEL = ["OK", "Cancel"]
    YES_NO = ["Yes", "No"]
    YES_NO_CANCEL = ["Yes", "No", "Cancel"]


_TYPE_ICONS = {
    "info":     "\u2139",   # ℹ
    "warning":  "\u26A0",   # ⚠
    "error":    "\u2716",   # ✖
    "question": "\u2753",   # ❓
}

_TYPE_COLORS = {
    "info":     (0.3, 0.6, 0.9, 1.0),
    "warning":  (0.9, 0.7, 0.2, 1.0),
    "error":    (0.9, 0.3, 0.3, 1.0),
    "question": (0.3, 0.8, 0.5, 1.0),
}


class MessageBox(Dialog):
    """Pre-built modal message dialog.

    Usage::

        MessageBox.info(ui, "Done", "Operation completed.")
        MessageBox.error(ui, "Error", "File not found.", on_result=handle)
        MessageBox.question(ui, "Confirm", "Delete?", on_result=handle)

    ``on_result`` receives the button label: ``"OK"``, ``"Cancel"``, ``"Yes"``, ``"No"``.
    """

    def __init__(self):
        super().__init__()
        self.message_type: str = "info"
        self.message: str = ""
        self.icon_font_size: float = 28
        self.message_font_size: float = _t.font_size
        self.min_width: float = 340

    # ------------------------------------------------------------------
    # Build content: icon + message
    # ------------------------------------------------------------------

    def _build(self):
        from tcgui.widgets.label import Label
        from tcgui.widgets.hstack import HStack

        layout = HStack()
        layout.spacing = 14
        layout.alignment = "center"

        # Icon
        icon_label = Label()
        icon_label.text = _TYPE_ICONS.get(self.message_type, _TYPE_ICONS["info"])
        icon_label.font_size = self.icon_font_size
        icon_label.color = _TYPE_COLORS.get(self.message_type, _TYPE_COLORS["info"])
        layout.add_child(icon_label)

        # Message
        msg_label = Label()
        msg_label.text = self.message
        msg_label.font_size = self.message_font_size
        msg_label.color = _t.text_primary
        layout.add_child(msg_label)

        self.content = layout

        # Build buttons via parent
        super()._build()

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @staticmethod
    def info(ui, title: str, message: str, *,
             buttons: list[str] | None = None,
             on_result: Callable[[str], None] | None = None) -> MessageBox:
        """Show an informational message box."""
        return MessageBox._create(ui, "info", title, message,
                                  buttons or Buttons.OK, "OK", on_result)

    @staticmethod
    def warning(ui, title: str, message: str, *,
                buttons: list[str] | None = None,
                on_result: Callable[[str], None] | None = None) -> MessageBox:
        """Show a warning message box."""
        return MessageBox._create(ui, "warning", title, message,
                                  buttons or Buttons.OK, "OK", on_result)

    @staticmethod
    def error(ui, title: str, message: str, *,
              buttons: list[str] | None = None,
              on_result: Callable[[str], None] | None = None) -> MessageBox:
        """Show an error message box."""
        return MessageBox._create(ui, "error", title, message,
                                  buttons or Buttons.OK, "OK", on_result)

    @staticmethod
    def question(ui, title: str, message: str, *,
                 buttons: list[str] | None = None,
                 on_result: Callable[[str], None] | None = None) -> MessageBox:
        """Show a question / confirmation message box."""
        return MessageBox._create(ui, "question", title, message,
                                  buttons or Buttons.YES_NO, "Yes", on_result)

    @staticmethod
    def _create(ui, msg_type: str, title: str, message: str,
                buttons: list[str], default: str,
                on_result: Callable[[str], None] | None) -> MessageBox:
        mb = MessageBox()
        mb.message_type = msg_type
        mb.title = title
        mb.message = message
        mb.buttons = buttons
        mb.default_button = default
        if len(buttons) > 1:
            mb.cancel_button = buttons[-1]
        mb.on_result = on_result
        mb.show(ui)
        return mb
